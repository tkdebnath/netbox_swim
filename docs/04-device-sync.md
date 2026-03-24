# Device Synchronization

SWIM connects to devices over SSH (using Scrapli, Netmiko, or pyATS) to collect facts like firmware version, hardware model, serial number, and flash capacity. These facts are stored as NetBox custom fields.

## 1. Custom Fields
The sync process creates and populates these custom fields on `dcim.Device` automatically:
- `swim_running_version`
- `swim_hardware_model`
- `swim_serial_number`
- `swim_flash_total_mb` / `swim_flash_free_mb`
- `swim_last_sync_status`
- `swim_last_successful_sync`

## 2. Sync Modes
- **Auto Update** (`auto_update=True`): Parsed facts are written directly to the device's custom fields without review.
- **Manual Review** (`auto_update=False`): Facts are stored in a `DeviceSyncRecord` with status "Pending Review". An admin must approve the diff before it gets written to the device record.

---

## 3. API Endpoints

### Triggering a Bulk Sync
- **Endpoint:** `/api/plugins/swim/sync-jobs/execute_bulk_sync/`
- **Method:** `POST`

```python
import requests
import time
HEADERS = {"Authorization": "Token <YOUR_TOKEN>", "Content-Type": "application/json"}

# 1. Start a sync job for devices 11 and 12
req = requests.post("http://<netbox>/api/plugins/swim/sync-jobs/execute_bulk_sync/", headers=HEADERS, json={
    "device_ids": [11, 12],
    "connection_library": "scrapli",
    "auto_update": False  # Creates DeviceSyncRecord objects for manual review
})

# The response includes a tracking URL
job_url = req.json()['url'] 

# 2. Poll until job completes
while True:
    status = requests.get(job_url, headers=HEADERS).json()
    print(f"[{status['status']}] Success: {status['selected_device_count'] - status['failed_device_count']}")
    
    if status['status'] in ['completed', 'failed', 'errored']:
        break
    time.sleep(5)
```

### Approving a Sync Diff (Manual Mode)
When `auto_update=False`, you need to approve each `DeviceSyncRecord` before its data gets written to the device.

- **Endpoint:** `/api/plugins/swim/sync-records/<PK>/approve/`
- **Method:** `POST`

```python
# Approve sync record PK 99
requests.post("http://<netbox>/api/plugins/swim/sync-records/99/approve/", headers=HEADERS)
```
