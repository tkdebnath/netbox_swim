#!/usr/bin/env python3
"""
Upgrade devices — run single/bulk upgrades, monitor jobs, cancel.

Usage:
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=your-token

    # Run upgrade for a single job
    python 03_upgrade_device.py --run --job-id 1

    # Bulk upgrade multiple devices
    python 03_upgrade_device.py --bulk --device-ids 1,2,3

    # Bulk upgrade with scheduling
    python 03_upgrade_device.py --bulk --device-ids 1,2,3 --scheduled "2026-03-30T02:00:00Z"

    # Check single job status
    python 03_upgrade_device.py --status --job-id 1

    # Monitor single job until done
    python 03_upgrade_device.py --monitor --job-id 1

    # Monitor ALL running upgrade jobs (dashboard view)
    python 03_upgrade_device.py --dashboard

    # Cancel a job
    python 03_upgrade_device.py --cancel --job-id 1

    # Dry run (shows what would happen without executing)
    python 03_upgrade_device.py --dry-run --job-id 1

    # List recent upgrade jobs
    python 03_upgrade_device.py --list
"""

import os
import sys
import time
import argparse
import requests

BASE_URL = os.environ.get("NETBOX_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN", "")
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}


# ---- Single Job Operations ----

def run_upgrade(job_id, connection_library=None):
    """Start a single upgrade job."""
    payload = {}
    if connection_library:
        payload["connection_priority"] = connection_library

    r = requests.post(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/run/",
                      headers=HEADERS, json=payload)
    if r.status_code == 200:
        print(f"OK   Upgrade job #{job_id} started")
        print(f"     {r.json()}")
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def get_job_status(job_id):
    """Get the status of a single upgrade job."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/", headers=HEADERS)
    if r.status_code != 200:
        print(f"FAIL: {r.status_code}")
        return None

    job = r.json()
    device = job.get("device", {})
    device_name = device.get("display", device) if isinstance(device, dict) else device
    image = job.get("target_image", {})
    image_name = image.get("display", image) if isinstance(image, dict) else image

    print(f"\n--- Upgrade Job #{job_id} ---")
    print(f"Device:    {device_name}")
    print(f"Image:     {image_name}")
    print(f"Status:    {job['status']}")
    print(f"Started:   {job.get('start_time', 'N/A')}")
    print(f"Ended:     {job.get('end_time', 'N/A')}")

    # Show step logs
    logs = requests.get(f"{BASE_URL}/api/plugins/swim/job-logs/?job_id={job_id}&limit=50",
                        headers=HEADERS)
    if logs.status_code == 200:
        entries = logs.json().get("results", [])
        if entries:
            print(f"\nStep Logs ({len(entries)} entries):")
            for log in reversed(entries):  # oldest first
                status = "PASS" if log.get("is_success") else "FAIL"
                print(f"  [{status}] {log.get('action_type', '?')} — {log.get('timestamp', '')}")

    return job


def cancel_job(job_id):
    """Cancel an upgrade job (sends hard-kill to worker)."""
    r = requests.post(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/cancel/",
                      headers=HEADERS)
    if r.status_code == 200:
        print(f"OK   Job #{job_id} cancelled — {r.json()}")
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def dry_run(job_id):
    """Preview the execution pipeline without running."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/dry_run/",
                     headers=HEADERS)
    if r.status_code == 200:
        plan = r.json().get("pipeline_plan", [])
        print(f"\n--- Dry Run: Job #{job_id} ---")
        if isinstance(plan, list):
            for step in plan:
                print(f"  Step {step.get('order', '?'):>3}: {step.get('action', '?')}")
        else:
            print(plan)
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def monitor_job(job_id, interval=5):
    """Monitor a single job until it completes."""
    print(f"Monitoring Upgrade Job #{job_id} (every {interval}s)...\n")
    while True:
        job = get_job_status(job_id)
        if not job:
            break

        status = job.get("status", "").lower()
        if status in ("completed", "failed", "cancelled"):
            print(f"\nJob #{job_id} finished: {status}")
            break

        print(f"\n... waiting {interval}s ...")
        time.sleep(interval)


# ---- Bulk Operations ----

def bulk_upgrade(device_ids, connection_library="scrapli", execution_mode="execute",
                 scheduled_time=None):
    """Start bulk upgrade for multiple devices."""
    payload = {
        "device_ids": device_ids,
        "connection_library": connection_library,
        "execution_mode": execution_mode,
    }
    if scheduled_time:
        payload["scheduled_time"] = scheduled_time

    r = requests.post(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/execute_bulk_remediation/",
                      headers=HEADERS, json=payload)
    if r.status_code == 200:
        print(f"OK   Bulk upgrade queued for {len(device_ids)} device(s)")
        print(f"     {r.json()}")
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


# ---- Dashboard: Show all active jobs ----

def dashboard(interval=10):
    """Continuously show all running/pending upgrade jobs."""
    print(f"SWIM Upgrade Dashboard (refreshing every {interval}s, Ctrl+C to exit)\n")

    while True:
        r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/?limit=50", headers=HEADERS)
        if r.status_code != 200:
            print(f"FAIL: {r.status_code}")
            break

        jobs = r.json().get("results", [])
        active = [j for j in jobs if j["status"] in ("pending", "running", "scheduled")]
        recent = [j for j in jobs if j["status"] in ("completed", "failed", "cancelled")][:5]

        os.system("clear" if os.name != "nt" else "cls")
        print(f"{'='*70}")
        print(f"  SWIM Upgrade Dashboard — {time.strftime('%H:%M:%S')}")
        print(f"{'='*70}")

        if active:
            print(f"\n  ACTIVE JOBS ({len(active)}):")
            print(f"  {'ID':>5}  {'Status':<12}  {'Device':<20}  {'Started'}")
            print(f"  {'-'*60}")
            for j in active:
                device = j.get("device", {})
                name = device.get("display", "?") if isinstance(device, dict) else str(device)
                print(f"  {j['id']:>5}  {j['status']:<12}  {name:<20}  {j.get('start_time', 'N/A')}")
        else:
            print("\n  No active jobs.")

        if recent:
            print(f"\n  RECENT COMPLETED ({len(recent)}):")
            print(f"  {'ID':>5}  {'Status':<12}  {'Device':<20}  {'Ended'}")
            print(f"  {'-'*60}")
            for j in recent:
                device = j.get("device", {})
                name = device.get("display", "?") if isinstance(device, dict) else str(device)
                print(f"  {j['id']:>5}  {j['status']:<12}  {name:<20}  {j.get('end_time', 'N/A')}")

        # Stop polling if no active jobs
        if not active:
            print("\nAll jobs finished.")
            break

        time.sleep(interval)


# ---- List Jobs ----

def list_jobs(limit=20):
    """Show recent upgrade jobs."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/?limit={limit}", headers=HEADERS)
    if r.status_code != 200:
        print(f"FAIL: {r.status_code}")
        return

    jobs = r.json().get("results", [])
    print(f"\n--- Recent Upgrade Jobs (last {limit}) ---")
    print(f"{'ID':>5}  {'Status':<12}  {'Device':<20}  {'Image':<25}  {'Started'}")
    print("-" * 80)
    for j in jobs:
        device = j.get("device", {})
        name = device.get("display", "?") if isinstance(device, dict) else str(device)
        image = j.get("target_image", {})
        img_name = image.get("display", "?") if isinstance(image, dict) else str(image)
        print(f"{j['id']:>5}  {j['status']:<12}  {name:<20}  {img_name:<25}  {j.get('start_time', 'N/A')}")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWIM Upgrade Operations")
    parser.add_argument("--run", action="store_true", help="Run a single upgrade job")
    parser.add_argument("--bulk", action="store_true", help="Bulk upgrade multiple devices")
    parser.add_argument("--status", action="store_true", help="Check job status")
    parser.add_argument("--monitor", action="store_true", help="Monitor job until done")
    parser.add_argument("--dashboard", action="store_true", help="Live dashboard of all jobs")
    parser.add_argument("--cancel", action="store_true", help="Cancel a running job")
    parser.add_argument("--dry-run", action="store_true", dest="dryrun", help="Preview pipeline")
    parser.add_argument("--list", action="store_true", help="List recent upgrade jobs")
    parser.add_argument("--job-id", type=int, default=None, help="Upgrade job ID")
    parser.add_argument("--device-ids", type=str, default="", help="Comma-separated device IDs")
    parser.add_argument("--library", type=str, default="scrapli", help="Connection library")
    parser.add_argument("--mode", type=str, default="execute",
                        help="Execution mode: execute, dry_run, mock_run")
    parser.add_argument("--scheduled", type=str, default=None,
                        help="Schedule time ISO-8601 (e.g. 2026-03-30T02:00:00Z)")
    args = parser.parse_args()

    if args.run:
        if not args.job_id:
            print("ERROR: Provide --job-id"); sys.exit(1)
        run_upgrade(args.job_id, args.library)

    elif args.bulk:
        ids = [int(x) for x in args.device_ids.split(",") if x.strip()]
        if not ids:
            print("ERROR: Provide --device-ids"); sys.exit(1)
        bulk_upgrade(ids, args.library, args.mode, args.scheduled)

    elif args.status:
        if not args.job_id:
            print("ERROR: Provide --job-id"); sys.exit(1)
        get_job_status(args.job_id)

    elif args.monitor:
        if not args.job_id:
            print("ERROR: Provide --job-id"); sys.exit(1)
        monitor_job(args.job_id)

    elif args.dashboard:
        dashboard()

    elif args.cancel:
        if not args.job_id:
            print("ERROR: Provide --job-id"); sys.exit(1)
        cancel_job(args.job_id)

    elif args.dryrun:
        if not args.job_id:
            print("ERROR: Provide --job-id"); sys.exit(1)
        dry_run(args.job_id)

    elif args.list:
        list_jobs()

    else:
        parser.print_help()
