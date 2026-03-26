# Developer & Maintenance Guide

This page covers the codebase structure, how to add new platform support, common troubleshooting, and maintenance procedures.

---

## Project Structure

```
netbox_swim/
├── setup.py                      # Python package definition
├── Dockerfile-Custom             # Custom NetBox Docker image with SWIM dependencies
├── seed_custom_fields.py         # Registers SWIM custom fields on dcim.Device
├── seed_swim.py                  # Legacy device seeder
├── make_migs.py                  # Django migration helper
│
├── data_seed/                    # JSON seed files + loader script
│   ├── 01–13_*.json              # Numbered JSON payloads (see User Guide)
│   └── load_seed_data.py         # Idempotent API-based data loader
│
├── rest_api/                     # Standalone CLI automation scripts
│   ├── 01_add_device.py          # Add devices via API
│   ├── 02_sync_device.py         # Sync + monitor
│   ├── 03_upgrade_device.py      # Upgrade + monitor
│   └── 04_download_files.py      # Download archives
│
├── docs/confluence/              # This documentation
│
└── netbox_swim/                  # Django plugin package
    ├── __init__.py               # Plugin config + custom field auto-registration
    ├── models.py                 # All database models (5 pillars)
    ├── engine.py                 # Core execution engine (sync, upgrade, archive)
    ├── views.py                  # UI views (list, detail, forms, bulk actions)
    ├── urls.py                   # URL routing
    ├── tables.py                 # Django Tables2 definitions
    ├── forms.py                  # Django forms
    ├── filtersets.py             # REST API + UI filters
    ├── navigation.py             # Plugin menu structure
    ├── constants.py              # Platform mappings + custom field registry
    ├── compliance.py             # Compliance evaluation logic
    ├── swim_logger.py            # Structured logging utilities
    ├── testbed.py                # pyATS testbed YAML generator
    ├── template_content.py       # NetBox template extensions
    │
    ├── api/                      # REST API
    │   ├── views.py              # ViewSets
    │   ├── serializers.py        # DRF Serializers
    │   └── urls.py               # API URL routing
    │
    ├── parsers/                  # CLI output parsers
    │   ├── cisco.py              # CiscoShowVersionParser, InventoryParser, TacacsParser
    │   └── base.py               # Base parser class
    │
    ├── tasks/                    # SSH task executors
    │   ├── base.py               # ScrapliTask, NetmikoTask, UniconTask base classes
    │   ├── sync/cisco.py         # Sync executors (3 libraries × Cisco)
    │   ├── readiness/cisco.py    # Flash/RAM readiness checks
    │   ├── distribution/cisco.py # Image copy to device
    │   ├── activation/cisco.py   # Install + reload
    │   ├── checks/cisco.py       # Pre/post operational checks
    │   └── verification/cisco.py # Post-upgrade version verification
    │
    ├── templates/                # Django HTML templates
    └── migrations/               # Database migrations
```

---

## How the Engine Works

### Key File: `engine.py`

This is the brain of the plugin. Here's what each major function does:

| Function | Purpose |
|----------|---------|
| `_sync_device_logic()` | Core sync flow for a single device (select library → SSH → parse → diff → save) |
| `_finalize_sync_job()` | Sets final status on a SyncJob after single-device sync |
| `execute_sync_job()` | RQ job wrapper for single device sync |
| `execute_bulk_sync_batch()` | RQ job for bulk sync with ThreadPoolExecutor |
| `execute_bulk_remediation()` | RQ job that creates UpgradeJobs for multiple devices |
| `execute_upgrade_job()` | RQ job that runs the full workflow template step by step |
| `generate_pipeline_plan()` | Generates a human-readable execution plan for a job |
| `_generate_checks_archive()` | Builds the ZIP file with precheck/postcheck/diffs/job_log |
| `_generate_fallback_diff()` | Python difflib-based fallback when Genie CLI is unavailable |

### Task Inheritance

```
ScrapliTask (base.py)
 └── SyncCiscoIosDeviceScrapli (tasks/sync/cisco.py)
 └── ReadinessCiscoScrapli (tasks/readiness/cisco.py)
 └── CiscoDistributeScrapli (tasks/distribution/cisco.py)
 └── CiscoActivateScrapli (tasks/activation/cisco.py)
 └── CiscoChecksScrapli (tasks/checks/cisco.py)
 └── CiscoVerifyScrapli (tasks/verification/cisco.py)

NetmikoTask (base.py)
 └── [same pattern with Netmiko suffix]

UniconTask (base.py)
 └── [same pattern with Unicon suffix]
```

Each base class handles:
- Credential resolution (env vars, config context profiles)
- Platform slug → library-specific platform translation
- SSH connection lifecycle (connect/disconnect/error handling)

---

## Adding Support for a New Platform

### Step 1: Update Platform Mappings

In `constants.py`, add a new entry to `PLATFORM_MAPPINGS`:

```python
'fortinet-fortios': {
    'scrapli': 'fortinet_fortios',    # if scrapli supports it
    'netmiko': 'fortinet',
    'unicon': 'fortios',              # if unicon supports it
    'textfsm': 'fortinet',
    'genie': 'fortios'
},
```

### Step 2: Create Parsers

In `parsers/`, create a new parser file (e.g. `fortinet.py`):

```python
class FortinetShowVersionParser:
    def __init__(self, raw_string, platform_slug=''):
        self.raw = raw_string
        self.platform_slug = platform_slug

    def get_facts(self):
        # Parse raw CLI output and return standardized schema
        return {
            'hostname': 'FW-01',
            'version': '7.2.4',
            'hardware': 'FortiGate-60F',
            'serial': 'FGT60FXXXXXXXX',
            'platform': 'FortiOS',
        }
```

### Step 3: Create Task Executors

In `tasks/sync/`, create `fortinet.py`:

```python
from ..base import NetmikoTask
from ...parsers.fortinet import FortinetShowVersionParser

class SyncFortinetDeviceNetmiko(NetmikoTask):
    def execute(self, device, target_image=None, auto_update=False):
        with self.connect(device) as conn:
            response = conn.send_command("get system status")
            parser = FortinetShowVersionParser(response, device.platform.slug)
            schema = parser.get_facts()
            return self._process_facts(device, schema, auto_update)
```

### Step 4: Register in Engine

In `engine.py`, update the platform detection logic in `_sync_device_logic()`:

```python
FORTINET_KEYWORDS = ('fortinet', 'fortios', 'fortigate')
is_fortinet = any(kw in platform_slug for kw in FORTINET_KEYWORDS)

if is_fortinet:
    task = SyncFortinetDeviceNetmiko()
```

And add to `TASK_REGISTRY` in `execute_upgrade_job()` if upgrade support is needed.

---

## Database Migrations

### Creating a New Migration

When you modify `models.py`:

```bash
# From the NetBox installation directory
python manage.py makemigrations netbox_swim

# Or use the helper script
python make_migs.py
```

### Applying Migrations

```bash
python manage.py migrate netbox_swim
```

### Migration Naming Convention

Migration files are auto-numbered. If adding a meaningful change, rename for clarity:
```
0024_add_firmware_checksum_field.py
```

---

## Environment Setup

### Docker Compose

The `Dockerfile-Custom` builds a custom NetBox image with SWIM dependencies:

```dockerfile
FROM netboxcommunity/netbox:latest
COPY . /opt/netbox/netbox/netbox-swim/
RUN pip install /opt/netbox/netbox/netbox-swim/
RUN pip install scrapli netmiko pyats genie
```

### Required Docker Environment Variables

```yaml
# docker-compose.override.yml
services:
  netbox:
    environment:
      - SWIM_USERNAME=admin
      - SWIM_PASSWORD=cisco123
  netbox-worker:
    environment:
      - SWIM_USERNAME=admin
      - SWIM_PASSWORD=cisco123
```

### Per-Profile Credentials

For devices requiring different credentials, set a config context on the device:

```json
{
  "swim": {
    "credential_profile": "DC_SWITCHES"
  }
}
```

Then set environment variables:
```bash
export DC_SWITCHES_USERNAME=dcadmin
export DC_SWITCHES_PASSWORD=dc_secret123
```

---

## Troubleshooting

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Sync records stuck at "Syncing" | Stale in-memory object overwriting DB status | Fixed in commit `87c925b` — ensure latest code is deployed |
| "name 'self' is not defined" in report step | `self` used in a standalone function | Fixed in commit `adf11f3` — ensure latest code is deployed |
| Blank output in readiness/distribution logs | Tuple unpacking bug in generator expression | Fixed in commit `bda8072` — ensure latest code is deployed |
| Job log missing from ZIP archive | `job_log.txt` not written before archiving | Fixed in commit `e248ff8` — ensure latest code is deployed |
| "No Primary IP assigned" abort | Device missing IP in NetBox | Assign a Primary IPv4/IPv6 under Devices → {device} → Interfaces |
| "Platform criteria did not match" abort | Platform slug doesn't contain Cisco keywords | Edit Platform → change slug to include `cisco`, `ios`, `nxos`, etc. |
| "Credentials missing" abort | Env vars not set on worker container | Set `SWIM_USERNAME` and `SWIM_PASSWORD` in Docker Compose |
| Import errors in IDE (dcim.models, django) | Local IDE doesn't have NetBox/Django in path | Expected — these resolve at runtime inside the NetBox container |

### Checking Worker Logs

```bash
# Docker
docker compose logs netbox-worker -f

# Systemd
journalctl -u netbox-rqworker -f
```

### Checking Job Status via API

```bash
# Upgrade job status
curl -s -H "Authorization: Token $NETBOX_TOKEN" \
  $NETBOX_URL/api/plugins/swim/upgrade-jobs/15/ | python3 -m json.tool

# Sync job status
curl -s -H "Authorization: Token $NETBOX_TOKEN" \
  $NETBOX_URL/api/plugins/swim/sync-jobs/5/ | python3 -m json.tool
```

---

## Code Style Guidelines

| Area | Convention |
|------|-----------|
| Comments | Technical and direct — avoid formal/verbose language |
| Docstrings | Single-line for simple functions, multi-line with Args: only when complex |
| Error messages | Include file/line reference, device name, and actionable fix suggestion |
| Logging | Use `logger.info/warning/error` with device name context |
| Variable naming | `snake_case` everywhere, descriptive names |
| Imports | Django/NetBox at top, stdlib lazy-imported where needed for performance |

---

## Maintenance Checklist

### Weekly
- [ ] Check RQ worker is running and processing jobs
- [ ] Review failed sync/upgrade jobs for recurring patterns
- [ ] Verify Redis connectivity

### Monthly
- [ ] Review compliance dashboard trends
- [ ] Update golden images if new firmware is released
- [ ] Check disk usage on file servers and media directory (ZIP archives)
- [ ] Review and clean up old sync records (older than 90 days)

### On New Firmware Release
1. Upload image binary to file server
2. Create SoftwareImage record (UI or API)
3. Update GoldenImage to point to new version
4. Run compliance check to identify non-compliant devices
5. Schedule upgrade jobs for non-compliant devices

### On New Device Type
1. Create DeviceType in NetBox if not auto-created
2. Add to appropriate HardwareGroup (platforms + device_types M2M)
3. Verify platform slug is recognized by SWIM
4. Test sync on a single device before bulk operations
