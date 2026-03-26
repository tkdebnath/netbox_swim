# REST API Scripts

Simple Python scripts to interact with SWIM via the NetBox REST API.
Just set your env vars and run.

```bash
export NETBOX_URL=http://localhost:8000
export NETBOX_TOKEN=your-api-token
```

| File | What it does |
|------|-------------|
| `01_add_device.py` | Add a device with IP, platform, site |
| `02_sync_device.py` | Sync devices, monitor, cancel |
| `03_upgrade_device.py` | Run upgrades, monitor jobs, download results |
| `04_download_files.py` | Download check archives and logs |

All scripts use `argparse` — run with `--help` to see options.
