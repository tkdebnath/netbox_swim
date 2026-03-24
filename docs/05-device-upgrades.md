# Upgrade Operations (Single & Bulk)

The upgrade engine takes a set of devices, matches them against Hardware Groups and Golden Images, then runs the assigned Workflow Template step-by-step.

## 1. Compliance (Read-Only)
The `DeviceCompliance` model compares each device's current firmware (from the last sync) against the Golden Image baseline. Records are maintained automatically—you only read them.

- **Endpoint:** `/api/plugins/swim/compliance/`
- **Methods:** `GET`

*Compliance records are managed by the system. Do not POST or PATCH directly.*

## 2. Upgrade Jobs
An `UpgradeJob` represents a single upgrade workflow targeting one device. The system prevents duplicate active jobs on the same device.

### Bulk Upgrade API
- **Endpoint:** `/api/plugins/swim/upgrade-jobs/execute_bulk_remediation/`
- **Method:** `POST`

**Execution Modes:**
- `execute`: Full SSH distribution, activation, and reload.
- `dry_run`: Runs pre/post checks over real SSH connections, but skips distribution and activation.
- `mock_run`: Simulates the entire workflow locally without any SSH connections.

```python
import requests
HEADERS = {"Authorization": "Token <YOUR_TOKEN>", "Content-Type": "application/json"}

queue_req = requests.post("http://<netbox>/api/plugins/swim/upgrade-jobs/execute_bulk_remediation/", headers=HEADERS, json={
    "device_ids": [15, 18, 55],
    "execution_mode": "dry_run",
    "connection_library": "scrapli"
})

print(queue_req.json())
# { "status": "Auto-Remediation Initiated", "devices_targeted": 3 }
```

### Dry Run Analysis (Per Job)
Returns a step-by-step preview of what the workflow will do, without executing anything.
- **Endpoint:** `/api/plugins/swim/upgrade-jobs/{PK}/dry_run/`
- **Method:** `GET`

```python
dry_run = requests.get("http://<netbox>/api/plugins/swim/upgrade-jobs/50/dry_run/", headers=HEADERS).json()
for output in dry_run["pipeline_plan"]:
    print(output)
# "[STEP 1 | distribution] -> Will execute CiscoDistributionScrapli using connection driver: SCRAPLI"
```

## 3. Job Logs
Each workflow step writes log entries to the `JobLog` table with timestamps and pass/fail results. You can poll these to monitor an upgrade in progress.

- **Endpoint:** `/api/plugins/swim/job-logs/`
- **Method:** `GET`

```python
# Poll logs for Job ID 50
import time
while True:
    logs = requests.get("http://<netbox>/api/plugins/swim/job-logs/?job_id=50", headers=HEADERS).json()['results']
    for log in logs:
        print(f"[{log['timestamp']}] {log['action_type']} -> {log['message']} ({log['result']})")
    
    time.sleep(10)
    # Break when the UpgradeJob status is 'completed' or 'failed'
```
