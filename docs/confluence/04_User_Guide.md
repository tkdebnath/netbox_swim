# User Guide

Step-by-step instructions for using the SWIM plugin.

---

## Prerequisites

Before using SWIM, ensure the following are in place:

| Requirement | Details |
|-------------|---------|
| **NetBox Version** | 4.x with plugin support enabled |
| **Redis** | Running and accessible for django-rq workers |
| **RQ Worker** | `python manage.py rqworker default` running in background |
| **SSH Credentials** | Set `SWIM_USERNAME` and `SWIM_PASSWORD` as environment variables on the worker container |
| **Device Primary IPs** | Every device you want to sync/upgrade must have a Primary IPv4 or IPv6 assigned in NetBox |
| **Platform Slugs** | Devices must have a Platform assigned with a slug containing a recognized keyword (e.g. `cisco`, `ios`, `nxos`) |

---

## 1. Initial Setup — Seed Data

The `data_seed/` folder contains 13 numbered JSON files that provision all plugin tables in the correct dependency order.

### Steps

1. Set environment variables:
   ```bash
   export NETBOX_URL=http://your-netbox:8000
   export NETBOX_TOKEN=your-api-token
   ```

2. Run the loader:
   ```bash
   cd data_seed/
   python load_seed_data.py
   ```

3. The script is **idempotent** — it skips objects that already exist and only creates missing ones.

### Load Order

| Step | File | What It Creates |
|------|------|-----------------|
| 01 | `01_manufacturers_platforms.json` | Cisco manufacturer + IOS-XE, NX-OS platforms |
| 02 | `02_device_types.json` | C9300, C9200, Nexus 9300, ISR, ASR models |
| 03 | `03_sites_regions.json` | Regions and Sites |
| 04 | `04_device_roles.json` | Core Switch, Access Switch, Router roles |
| 05 | `05_devices.json` | Sample devices with IPs |
| 06 | `06_file_servers.json` | HTTP, TFTP, SCP file servers |
| 07 | `07_validation_checks.json` | BGP, OSPF, Interface checks |
| 08 | `08_check_templates.json` | Bundled check templates |
| 09 | `09_workflow_templates.json` | Campus, SD-WAN, DC, Hotfix workflows |
| 10 | `10_workflow_steps.json` | Steps with connection_library preferences |
| 11 | `11_hardware_groups.json` | Hardware groups linked to platforms + templates |
| 12 | `12_software_images.json` | Firmware images with hashes |
| 13 | `13_golden_images.json` | Golden image baselines |

---

## 2. Syncing a Device

Sync collects live facts from a device via SSH and compares them against NetBox records.

### From the UI

1. Navigate to **OS & Firmware Upgrades → Bulk Device Sync**
2. Select devices from the table (use filters to narrow down)
3. Choose a connection library (Scrapli recommended for IOS-XE)
4. Set concurrency (default: 5)
5. Click **Submit Sync**

### From the CLI

```bash
cd rest_api/
python 02_sync_device.py --name "C9K-SWI01"           # Single device
python 02_sync_device.py --name "C9K-SWI01" --go       # Sync + monitor job
python 02_sync_device.py --site "SJ-HQ" --go           # All devices at a site
```

### What Gets Synced

| Field | Source Command | NetBox Field Updated |
|-------|---------------|---------------------|
| Hostname | `show version` / prompt | `device.name` |
| Hardware Model | `show version` | `device.device_type` |
| Serial Number | `show version` / `show inventory` | `device.serial` |
| Software Version | `show version` | `device.custom_field_data.software_version` |
| Platform | `show version` | `device.platform` |
| Part Number | `show inventory` | `device_type.part_number` |
| TACACS Source | `show running-config` | `device.custom_field_data.tacacs_source_interface` |

### Sync Record Statuses

| Status | Meaning |
|--------|---------|
| **Syncing** | SSH connection active, collecting facts |
| **No Change** | Device matches NetBox — no differences found |
| **Pending** | Differences found — awaiting manual approval |
| **Auto Applied** | Differences found and automatically applied (auto_update=True) |
| **Applied** | Manually approved by an operator |
| **Failed** | SSH connection or parsing error |
| **Aborted** | Pre-flight check failed (no IP, wrong platform, missing credentials) |

---

## 3. Approving Sync Changes

When a sync finds differences and `auto_update` is disabled:

1. Go to **Execution Engine → Consolidated Sync Results**
2. Click on the **Pending** record
3. Review the **Detected Diff** section showing old vs. new values
4. Click **Approve** to apply all changes to NetBox

---

## 4. Running an Upgrade

### From the UI

1. Navigate to **Execution Engine → Upgrade Jobs → Add**
2. Select the **Device** to upgrade
3. Select the **Target Image** (firmware version)
4. Select the **Workflow Template** (e.g. "Standard Campus Upgrade")
5. Optionally set a **Scheduled Time** for deferred execution
6. Click **Create**
7. The job executes each workflow step in order

### From the CLI

```bash
cd rest_api/
python 03_upgrade_device.py --name "C9K-SWI01" \
    --image "Cat9k-IOS-XE-17.09.05" \
    --template "Standard Campus Upgrade" \
    --go
```

The `--go` flag submits the job and starts real-time monitoring of each step.

### Upgrade Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Skips distribution/activation/verification (precheck + postcheck only) |
| `--mock-run` | No real SSH connections — all steps return mock success |
| `--connection-priority` | Override library order (e.g. `netmiko,scrapli`) |

---

## 5. Monitoring Job Progress

### UI

Each upgrade job page shows:

- **Job Execution Logs** — expandable per-step output with Pass/Fail badges
- **Engine Activity Timeline** — timestamped event log
- **pyATS Testbed** — generated YAML for the target device
- **Download Archive** — ZIP containing precheck, postcheck, diffs, and job_log.txt

### CLI

```bash
python 03_upgrade_device.py --name "C9K-SWI01" --go
# Output:
# [13:37:37] readiness     PASS
# [13:37:42] precheck      PASS
# [13:38:10] distribution  PASS
# [13:38:40] wait          PASS  (30s timer)
# [13:39:20] ping          PASS
# [13:39:50] postcheck     PASS
# [13:40:10] verification  PASS
# [13:40:20] report        PASS
# Job completed successfully.
```

---

## 6. Downloading Diagnostic Files

After a job completes, download the checks archive:

### UI
Click the **Download Archive** button on the upgrade job detail page.

### CLI
```bash
cd rest_api/
python 04_download_files.py --job-id 15
# Downloads: C9K-SWI01_checks_260326.zip
```

### Archive Contents

```
devicename_checks_ddmmyy.zip
├── precheck/          # Pre-upgrade operational state
├── postcheck/         # Post-upgrade operational state
├── diffs/             # Differences between pre and post
│   └── summary.log   # One-line summary per check
└── job_log.txt        # Full step-by-step execution log
```

---

## 7. Checking Compliance

1. Navigate to **Compliance & Workflows → Compliance Dashboard**
2. The dashboard shows:
   - Pie chart: Compliant vs. Non-Compliant vs. Unknown
   - Trend line: Compliance over time (from daily snapshots)
   - Table: Per-device compliance status

### How Compliance Is Calculated

A device is **compliant** if:
- It belongs to a HardwareGroup
- That group has a GoldenImage assigned
- The device's `software_version` custom field matches the golden image version

---

## 8. Managing Workflow Templates

### Built-in Templates

| Template | Steps |
|----------|-------|
| **Standard Campus Upgrade** | readiness → precheck → distribution → wait → ping → postcheck → verification → report |
| **SD-WAN Edge Upgrade** | readiness → precheck → distribution → activation → wait → ping → postcheck → verification → report |
| **Data Center Rolling Upgrade** | readiness → precheck → distribution → activation → wait → ping → postcheck → verification → report |
| **Emergency Hotfix** | readiness → distribution → activation → ping → verification |

### Creating Custom Templates

1. Go to **Compliance & Workflows → Workflow Templates → Add**
2. Name your template
3. Add steps with the desired order and action types
4. For SSH steps, set `extra_config` to specify connection_library:
   ```json
   {"connection_library": "netmiko"}
   ```
5. For wait steps:
   ```json
   {"duration": 300}
   ```
6. For ping steps:
   ```json
   {"retries": 10, "interval": 30}
   ```

---

## 9. pyATS Testbed Generator

Generate pyATS-compatible YAML testbeds for any device:

1. Go to **Execution Engine → pyATS Testbed Generator**
2. Select device(s)
3. Click **Generate**
4. Download the YAML file or copy from the UI

The testbed includes device IP, platform, credentials (from env vars), and connection parameters for all three SSH libraries.
