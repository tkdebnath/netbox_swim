#!/usr/bin/env python3
"""
Sync devices — start sync, check status, cancel, monitor until complete.

Usage:
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=your-token

    # Sync and monitor in one shot (submit + watch until done)
    python 02_sync_device.py --go --device-ids 1,2,3

    # Sync only (no monitoring)
    python 02_sync_device.py --sync --device-ids 1,2,3

    # Check sync job status
    python 02_sync_device.py --status --job-id 5

    # Monitor existing sync job until complete
    python 02_sync_device.py --monitor --job-id 5

    # Cancel a running sync
    python 02_sync_device.py --cancel --job-id 5
"""

import os
import sys
import time
import argparse
import requests

BASE_URL = os.environ.get("NETBOX_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN", "")
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}


# ---- Sync Operations ----

def start_sync(device_ids, connection_library="scrapli"):
    """Start a sync job for one or more devices."""
    payload = {
        "device_ids": device_ids,
        "connection_library": connection_library,
    }
    r = requests.post(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/execute_bulk_remediation/",
                      headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        print(f"OK   Sync started for {len(device_ids)} device(s)")
        print(f"     Response: {r.json()}")
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def get_sync_status(job_id):
    """Get current status of a sync job."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/sync-jobs/{job_id}/", headers=HEADERS)
    if r.status_code != 200:
        print(f"FAIL Cannot get job {job_id}: {r.status_code}")
        return None

    job = r.json()
    print(f"\n--- Sync Job #{job_id} ---")
    print(f"Status:          {job['status']}")
    print(f"Started:         {job.get('start_time', 'N/A')}")
    print(f"Ended:           {job.get('end_time', 'N/A')}")
    print(f"Devices:         {job.get('selected_device_count', 0)}")
    print(f"Failed:          {job.get('failed_device_count', 0)}")
    print(f"Connection Lib:  {job.get('connection_library', 'N/A')}")

    # Show per-device records
    records = requests.get(f"{BASE_URL}/api/plugins/swim/sync-records/?sync_job_id={job_id}",
                           headers=HEADERS)
    if records.status_code == 200:
        for rec in records.json().get("results", []):
            device_name = rec.get("device", {}).get("display", "?") if isinstance(rec.get("device"), dict) else rec.get("device")
            print(f"  [{rec.get('status', '?'):12s}] {device_name}")

    return job


def cancel_sync(job_id):
    """Cancel a running sync job."""
    # Update sync job status to cancelled
    r = requests.patch(f"{BASE_URL}/api/plugins/swim/sync-jobs/{job_id}/",
                       headers=HEADERS, json={"status": "cancelled"})
    if r.status_code == 200:
        print(f"OK   Sync job #{job_id} cancelled")
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def monitor_sync(job_id, interval=5):
    """Poll sync job status until it completes."""
    print(f"Monitoring Sync Job #{job_id} (every {interval}s)...\n")
    while True:
        job = get_sync_status(job_id)
        if not job:
            break

        status = job.get("status", "").lower()
        if status in ("completed", "failed", "cancelled", "done"):
            print(f"\nSync Job #{job_id} finished with status: {status}")
            break

        print(f"\n... waiting {interval}s ...")
        time.sleep(interval)


# ---- Submit + Monitor in one shot ----

def get_latest_sync_job_id():
    """Get the ID of the most recent sync job."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/sync-jobs/?limit=1", headers=HEADERS)
    if r.status_code == 200:
        jobs = r.json().get("results", [])
        if jobs:
            return jobs[0]["id"]
    return None


def sync_and_monitor(device_ids, connection_library="scrapli", interval=5):
    """Submit a sync job, find the new job, and monitor it until done."""

    # Remember the latest job ID before we submit
    old_latest = get_latest_sync_job_id()

    # Submit the sync
    payload = {
        "device_ids": device_ids,
        "connection_library": connection_library,
    }
    r = requests.post(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/execute_bulk_remediation/",
                      headers=HEADERS, json=payload)
    if r.status_code not in (200, 201):
        print(f"FAIL submitting sync: {r.status_code}: {r.text[:200]}")
        return

    print(f"OK   Sync submitted for {len(device_ids)} device(s)")

    # Wait a moment for the job to be created, then find the new job ID
    job_id = None
    for _ in range(10):
        time.sleep(2)
        new_latest = get_latest_sync_job_id()
        if new_latest and new_latest != old_latest:
            job_id = new_latest
            break

    if not job_id:
        print("WARN Could not detect new sync job ID. Check manually with --list")
        return

    print(f"OK   Detected new Sync Job #{job_id}")
    monitor_sync(job_id, interval)


# ---- List recent sync jobs ----

def list_sync_jobs(limit=10):
    """Show recent sync jobs."""
    r = requests.get(f"{BASE_URL}/api/plugins/swim/sync-jobs/?limit={limit}", headers=HEADERS)
    if r.status_code != 200:
        print(f"FAIL: {r.status_code}")
        return

    jobs = r.json().get("results", [])
    print(f"\n--- Recent Sync Jobs (last {limit}) ---")
    print(f"{'ID':>5}  {'Status':<15}  {'Devices':<8}  {'Failed':<8}  {'Started'}")
    print("-" * 70)
    for j in jobs:
        print(f"{j['id']:>5}  {j['status']:<15}  {j.get('selected_device_count', 0):<8}  "
              f"{j.get('failed_device_count', 0):<8}  {j.get('start_time', 'N/A')}")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWIM Sync Operations")
    parser.add_argument("--go", action="store_true", help="Submit sync + monitor until done (one shot)")
    parser.add_argument("--sync", action="store_true", help="Start a new sync (no monitoring)")
    parser.add_argument("--status", action="store_true", help="Check sync job status")
    parser.add_argument("--monitor", action="store_true", help="Monitor sync job until done")
    parser.add_argument("--cancel", action="store_true", help="Cancel a running sync")
    parser.add_argument("--list", action="store_true", help="List recent sync jobs")
    parser.add_argument("--device-ids", type=str, default="", help="Comma-separated device IDs")
    parser.add_argument("--job-id", type=int, default=None, help="Sync job ID")
    parser.add_argument("--library", type=str, default="scrapli", help="Connection library")
    args = parser.parse_args()

    if args.go:
        ids = [int(x) for x in args.device_ids.split(",") if x.strip()]
        if not ids:
            print("ERROR: Provide --device-ids (e.g. --device-ids 1,2,3)")
            sys.exit(1)
        sync_and_monitor(ids, args.library)

    elif args.sync:
        ids = [int(x) for x in args.device_ids.split(",") if x.strip()]
        if not ids:
            print("ERROR: Provide --device-ids (e.g. --device-ids 1,2,3)")
            sys.exit(1)
        start_sync(ids, args.library)

    elif args.status:
        if not args.job_id:
            print("ERROR: Provide --job-id")
            sys.exit(1)
        get_sync_status(args.job_id)

    elif args.monitor:
        if not args.job_id:
            print("ERROR: Provide --job-id")
            sys.exit(1)
        monitor_sync(args.job_id)

    elif args.cancel:
        if not args.job_id:
            print("ERROR: Provide --job-id")
            sys.exit(1)
        cancel_sync(args.job_id)

    elif args.list:
        list_sync_jobs()

    else:
        parser.print_help()
