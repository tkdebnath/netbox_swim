# Seed Data Files

JSON payloads for populating SWIM tables via the NetBox REST API.
Run them in order (01 → 13) since later files reference objects from earlier ones.

## How to load

Set your NetBox URL and token, then run the loader:

```bash
export NETBOX_URL=http://localhost:8000
export NETBOX_TOKEN=your-api-token
python data_seed/load_seed_data.py
```

The loader will skip anything that already exists, so it's safe to re-run.

## File list

| # | File | Creates |
|---|------|---------|
| 01 | `01_manufacturers_platforms.json` | Cisco + platforms (IOS-XE, NX-OS, etc.) |
| 02 | `02_device_types.json` | C9300, C9200, Nexus 9K, ASR, ISR models |
| 03 | `03_sites_regions.json` | US-West, US-East, APAC regions + sites |
| 04 | `04_device_roles.json` | Core, Access, Edge, Spine, Leaf roles |
| 05 | `05_devices.json` | Sample devices across all sites |
| 06 | `06_file_servers.json` | HTTP, TFTP, SCP, HTTPS file servers |
| 07 | `07_validation_checks.json` | BGP, OSPF, CDP, NTP, flash, STP checks |
| 08 | `08_check_templates.json` | Grouped check templates per use case |
| 09 | `09_workflow_templates.json` | Campus, SD-WAN, DC, Hotfix workflows |
| 10 | `10_workflow_steps.json` | Step ordering for each workflow |
| 11 | `11_hardware_groups.json` | Fleet segments with workflow bindings |
| 12 | `12_software_images.json` | Firmware images with hash/size info |
| 13 | `13_golden_images.json` | Compliance baselines |

Files 08-13 use placeholder tokens (like `__TEMPLATE_ID_CAMPUS__`) for cross-references.
The `load_seed_data.py` script resolves these automatically by looking up names in the API.
