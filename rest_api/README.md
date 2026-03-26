# SWIM REST API — Operation Scripts

Simple Python scripts for common SWIM operations via REST API.
Each file is standalone — just set `NETBOX_URL` and `NETBOX_TOKEN` and run.

## Setup

```bash
export NETBOX_URL=http://localhost:8000
export NETBOX_TOKEN=your-api-token-here
```

## Scripts

| File | What it does |
|------|-------------|
| `01_add_device.py` | Add a new device to NetBox with IP, platform, site |
| `02_sync_device.py` | Sync one or multiple devices, check status, cancel |
| `03_upgrade_device.py` | Upgrade one or multiple devices, monitor progress |
| `04_download_files.py` | Download check archives, logs, fragments |
