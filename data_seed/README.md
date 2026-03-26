# SWIM Plugin – Seed Data Files

Each numbered JSON file contains sample payloads to populate the SWIM plugin tables
via the NetBox REST API. **Execute them in order** since later files reference IDs
created by earlier ones.

## Base URL

```
http://<netbox-host>/api/
```

All requests require an `Authorization: Token <your-token>` header.

## Execution Order

| # | File | API Endpoint | Purpose |
|---|------|--------------|---------|
| 01 | `01_manufacturers_platforms.json` | `/api/dcim/manufacturers/` + `/api/dcim/platforms/` | Core NetBox prerequisites |
| 02 | `02_device_types.json` | `/api/dcim/device-types/` | Hardware models |
| 03 | `03_sites_regions.json` | `/api/dcim/regions/` + `/api/dcim/sites/` | Locations |
| 04 | `04_device_roles.json` | `/api/dcim/device-roles/` | Functional roles |
| 05 | `05_devices.json` | `/api/dcim/devices/` | Network devices |
| 06 | `06_file_servers.json` | `/api/plugins/swim/file-servers/` | Image distribution servers |
| 07 | `07_validation_checks.json` | `/api/plugins/swim/validation-checks/` | Genie/CLI check definitions |
| 08 | `08_check_templates.json` | `/api/plugins/swim/check-templates/` | Grouped validation templates |
| 09 | `09_workflow_templates.json` | `/api/plugins/swim/workflow-templates/` | Upgrade lifecycle definitions |
| 10 | `10_workflow_steps.json` | `/api/plugins/swim/workflow-steps/` | Pipeline step ordering |
| 11 | `11_hardware_groups.json` | `/api/plugins/swim/hardware-groups/` | Device fleet segmentation |
| 12 | `12_software_images.json` | `/api/plugins/swim/software-images/` | Firmware image catalog |
| 13 | `13_golden_images.json` | `/api/plugins/swim/golden-images/` | Compliance baselines |

## Quick Load (curl)

```bash
TOKEN="your-netbox-api-token"
BASE="http://localhost:8000"

for f in data_seed/0*.json data_seed/1*.json; do
  ENDPOINT=$(head -3 "$f" | grep '"_endpoint"' | cut -d'"' -f4)
  echo "Loading $f -> $ENDPOINT"
  curl -s -X POST "${BASE}${ENDPOINT}" \
    -H "Authorization: Token $TOKEN" \
    -H "Content-Type: application/json" \
    -d @"$f"
  echo ""
done
```

> **Note:** For files with multiple objects, post each entry in the `"data"` array individually,
> or use the NetBox bulk-create endpoint (POST an array directly).
