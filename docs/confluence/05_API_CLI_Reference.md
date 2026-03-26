# API & CLI Reference

This page documents the plugin's REST API endpoints and the CLI automation scripts.

---

## REST API Endpoints

All plugin endpoints are prefixed with `/api/plugins/swim/`.

### Image Repository

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins/swim/software-images/` | List all software images |
| POST | `/api/plugins/swim/software-images/` | Create a new software image |
| GET | `/api/plugins/swim/software-images/{id}/` | Get image details |
| PATCH | `/api/plugins/swim/software-images/{id}/` | Update image (including M2M fields) |
| DELETE | `/api/plugins/swim/software-images/{id}/` | Delete an image |
| GET | `/api/plugins/swim/file-servers/` | List file servers |
| POST | `/api/plugins/swim/file-servers/` | Create a file server |
| GET | `/api/plugins/swim/golden-images/` | List golden images |
| POST | `/api/plugins/swim/golden-images/` | Create a golden image |

### Hardware & Compliance

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins/swim/hardware-groups/` | List hardware groups |
| POST | `/api/plugins/swim/hardware-groups/` | Create a hardware group |
| PATCH | `/api/plugins/swim/hardware-groups/{id}/` | Update (platforms, device_types M2M) |
| GET | `/api/plugins/swim/device-compliance/` | List compliance records |
| GET | `/api/plugins/swim/validation-checks/` | List validation checks |
| GET | `/api/plugins/swim/check-templates/` | List check templates |

### Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins/swim/workflow-templates/` | List workflow templates |
| POST | `/api/plugins/swim/workflow-templates/` | Create a template |
| GET | `/api/plugins/swim/workflow-steps/` | List workflow steps |
| POST | `/api/plugins/swim/workflow-steps/` | Create a step |

### Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins/swim/upgrade-jobs/` | List upgrade jobs |
| POST | `/api/plugins/swim/upgrade-jobs/` | Submit a new upgrade job |
| GET | `/api/plugins/swim/upgrade-jobs/{id}/` | Get job details + status |
| GET | `/api/plugins/swim/job-logs/` | List execution logs |
| GET | `/api/plugins/swim/job-logs/?job_id={id}` | Logs for a specific job |

### Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins/swim/sync-jobs/` | List sync jobs |
| GET | `/api/plugins/swim/sync-records/` | List device sync records |
| POST | `/api/plugins/swim/sync-records/{id}/approve/` | Approve a pending sync record |

---

## Authentication

All API calls require a NetBox API token in the `Authorization` header:

```bash
curl -H "Authorization: Token your-api-token-here" \
     http://netbox:8000/api/plugins/swim/software-images/
```

---

## Example API Payloads

### Create a Software Image

```json
POST /api/plugins/swim/software-images/
{
    "image_name": "Cat9k-IOS-XE-17.09.05",
    "image_file_name": "cat9k_iosxe.17.09.05.SPA.bin",
    "version": "17.09.05",
    "image_type": "software",
    "platform": 1,
    "file_server": 1,
    "deployment_mode": "campus",
    "file_size_bytes": 1073741824,
    "hash_md5": "a1b2c3d4e5f67890abcdef1234567890",
    "hash_sha512": "cf83e1357eefb8bdf1542850d66d800..."
}
```

### Submit an Upgrade Job

```json
POST /api/plugins/swim/upgrade-jobs/
{
    "device": 5,
    "target_image": 1,
    "template": 1,
    "extra_config": {
        "dry_run": false,
        "mock_run": false,
        "connection_priority_override": "scrapli,netmiko"
    }
}
```

### Trigger Bulk Sync (UI endpoint)

```json
POST /plugins/swim/bulk-sync/submit/
{
    "device_ids": [1, 2, 3, 4, 5],
    "connection_library": "scrapli",
    "max_concurrency": 5,
    "auto_update": false
}
```

---

## CLI Automation Scripts

Located in the `rest_api/` folder. All scripts read `NETBOX_URL` and `NETBOX_TOKEN` from environment variables.

### 01_add_device.py — Add a Device

```bash
# Add a new device with all required fields
python 01_add_device.py \
    --name "SW-FLOOR3-01" \
    --device-type "Catalyst 9300-48P" \
    --site "SJ-HQ" \
    --role "Access Switch" \
    --platform "Cisco IOS-XE" \
    --ip "10.1.3.10/24"
```

### 02_sync_device.py — Sync Devices

```bash
# Sync a single device
python 02_sync_device.py --name "C9K-SWI01"

# Sync + monitor the job until completion
python 02_sync_device.py --name "C9K-SWI01" --go

# Sync all devices at a site
python 02_sync_device.py --site "SJ-HQ" --go

# Sync with a specific library
python 02_sync_device.py --name "C9K-SWI01" --library netmiko --go

# Cancel a running sync
python 02_sync_device.py --cancel --job-id 42

# Check status of a sync job
python 02_sync_device.py --status --job-id 42
```

### 03_upgrade_device.py — Upgrade Firmware

```bash
# Submit an upgrade job
python 03_upgrade_device.py \
    --name "C9K-SWI01" \
    --image "Cat9k-IOS-XE-17.09.05" \
    --template "Standard Campus Upgrade"

# Submit + monitor in real-time
python 03_upgrade_device.py \
    --name "C9K-SWI01" \
    --image "Cat9k-IOS-XE-17.09.05" \
    --template "Standard Campus Upgrade" \
    --go

# Dry run (no actual firmware changes)
python 03_upgrade_device.py \
    --name "C9K-SWI01" \
    --image "Cat9k-IOS-XE-17.09.05" \
    --template "Standard Campus Upgrade" \
    --dry-run --go

# Check status of an upgrade job
python 03_upgrade_device.py --status --job-id 15
```

### 04_download_files.py — Download Archives

```bash
# Download checks archive for a completed job
python 04_download_files.py --job-id 15

# Download to a specific directory
python 04_download_files.py --job-id 15 --output-dir /tmp/archives/

# List available downloads for a job
python 04_download_files.py --job-id 15 --list
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NETBOX_URL` | Yes | NetBox instance URL (e.g. `http://192.168.5.180:8000`) |
| `NETBOX_TOKEN` | Yes | API authentication token |
| `SWIM_USERNAME` | Yes (worker) | SSH username for device connections |
| `SWIM_PASSWORD` | Yes (worker) | SSH password for device connections |
| `{PROFILE}_USERNAME` | Optional | Per-profile SSH username (set via config context `swim.credential_profile`) |
| `{PROFILE}_PASSWORD` | Optional | Per-profile SSH password |
