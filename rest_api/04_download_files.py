#!/usr/bin/env python3
"""
Download files from upgrade jobs — check archives, fragments, execution logs.

Usage:
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=your-token

    # Download full checks archive (precheck + postcheck + diffs)
    python 04_download_files.py --checks --job-id 1

    # Download only precheck files
    python 04_download_files.py --fragment precheck --job-id 1

    # Download only postcheck files
    python 04_download_files.py --fragment postcheck --job-id 1

    # Download only diff files
    python 04_download_files.py --fragment diffs --job-id 1

    # Download execution logs as text
    python 04_download_files.py --logs --job-id 1

    # Download everything for a job
    python 04_download_files.py --all --job-id 1

    # Save to specific folder
    python 04_download_files.py --checks --job-id 1 --output-dir ./downloads
"""

import os
import sys
import argparse
import requests

BASE_URL = os.environ.get("NETBOX_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN", "")
HEADERS = {"Authorization": f"Token {TOKEN}"}


def save_file(response, output_dir):
    """Save the response content to a file using the filename from headers."""
    os.makedirs(output_dir, exist_ok=True)

    # Get filename from Content-Disposition header
    cd = response.headers.get("Content-Disposition", "")
    filename = "download"
    if 'filename="' in cd:
        filename = cd.split('filename="')[1].rstrip('"')
    elif "filename=" in cd:
        filename = cd.split("filename=")[1].strip()

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(response.content)

    size_kb = len(response.content) / 1024
    print(f"OK   Saved: {filepath} ({size_kb:.1f} KB)")
    return filepath


def download_checks(job_id, output_dir):
    """Download the full checks archive (precheck + postcheck + diffs ZIP)."""
    print(f"Downloading checks archive for job #{job_id}...")
    r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/download_checks/",
                     headers=HEADERS)
    if r.status_code == 200:
        save_file(r, output_dir)
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def download_fragment(job_id, fragment, output_dir):
    """Download a specific fragment (precheck, postcheck, or diffs)."""
    print(f"Downloading {fragment} fragment for job #{job_id}...")
    r = requests.get(
        f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/download_fragment/?fragment={fragment}",
        headers=HEADERS
    )
    if r.status_code == 200:
        save_file(r, output_dir)
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def download_logs(job_id, output_dir):
    """Download execution logs as plain text."""
    print(f"Downloading execution logs for job #{job_id}...")
    r = requests.get(f"{BASE_URL}/api/plugins/swim/upgrade-jobs/{job_id}/download_logs/",
                     headers=HEADERS)
    if r.status_code == 200:
        save_file(r, output_dir)
    else:
        print(f"FAIL {r.status_code}: {r.text[:200]}")


def download_all(job_id, output_dir):
    """Download everything for a job."""
    job_dir = os.path.join(output_dir, f"job_{job_id}")
    download_checks(job_id, job_dir)
    download_logs(job_id, job_dir)
    for frag in ["precheck", "postcheck", "diffs"]:
        download_fragment(job_id, frag, job_dir)
    print(f"\nAll files saved to: {job_dir}/")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWIM File Downloads")
    parser.add_argument("--checks", action="store_true", help="Download full checks archive")
    parser.add_argument("--fragment", type=str, default=None,
                        help="Download specific fragment: precheck, postcheck, diffs")
    parser.add_argument("--logs", action="store_true", help="Download execution logs")
    parser.add_argument("--all", action="store_true", help="Download everything")
    parser.add_argument("--job-id", type=int, required=True, help="Upgrade job ID")
    parser.add_argument("--output-dir", type=str, default="./downloads", help="Output directory")
    args = parser.parse_args()

    if args.all:
        download_all(args.job_id, args.output_dir)
    elif args.checks:
        download_checks(args.job_id, args.output_dir)
    elif args.fragment:
        download_fragment(args.job_id, args.fragment, args.output_dir)
    elif args.logs:
        download_logs(args.job_id, args.output_dir)
    else:
        parser.print_help()
