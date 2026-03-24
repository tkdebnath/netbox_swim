# NetBox SWIM (Software Image Management) Plugin

A NetBox plugin for managing firmware images, compliance baselines, and automated upgrade workflows across network infrastructure. Supports Scrapli, pyATS/Unicon, and Netmiko as connection backends.

## Features
- **Golden Image Definitions:** Define target software baselines scoped by Hardware Group or Device Type.
- **Device Sync & Diff:** Connects to devices via SSH, parses `show version` / `show inventory` / `dir flash:` output, and stores extracted facts as NetBox custom fields.
- **Workflow Templates:** Attach pre/post check sequences (e.g. `show ip bgp summary`, `show ip interface brief`) to upgrade pipelines.
- **Bulk Upgrades:** Queue non-compliant devices for firmware distribution and activation across sites, with dry-run and mock execution modes.

## Installation

### Docker (netbox-docker)
1. Add to `plugin_requirements.txt`:
   ```
   netbox-swim @ git+https://github.com/<your-org>/netbox-swim.git
   ```
2. Create `Dockerfile-Plugins`:
   ```dockerfile
   FROM netboxcommunity/netbox:latest
   COPY ./plugin_requirements.txt /opt/netbox/
   RUN /usr/local/bin/uv pip install --no-cache -r /opt/netbox/plugin_requirements.txt
   ```
3. Enable in `configuration/plugins.py`:
   ```python
   PLUGINS = ["netbox_swim"]
   ```
4. Set device credentials in `env/swim.env`:
   ```bash
   SWIM_USERNAME=your_ssh_user
   SWIM_PASSWORD=your_ssh_pass
   SWIM_SECRET=your_enable_secret
   ```
5. Build and start:
   ```bash
   docker compose build --no-cache && docker compose up -d
   ```

### Bare Metal
```bash
source /opt/netbox/venv/bin/activate
pip install netbox-swim                    # from PyPI
# OR: pip install git+https://github.com/<your-org>/netbox-swim.git
# OR: pip install -e /path/to/netbox-swim  # local development
cd /opt/netbox/netbox
python3 manage.py migrate
python3 manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

For the full setup guide (credential profiles, platform mapping, Docker upgrade process, troubleshooting), see [**Installation & Configuration**](docs/00-installation.md).

## Documentation

For detailed usage instructions, see the guides in the `docs/` folder:

0. [**Installation & Configuration**](docs/00-installation.md) – Plugin setup, credentials, platform mapping, custom fields, and troubleshooting.
1. [**Hardware Groups**](docs/01-hardware-groups.md) – Grouping platforms and device types, assigning workflow templates, and managing groups via API.
2. [**Software Images & File Servers**](docs/02-software-images.md) – Registering OS images, configuring file servers, setting up Golden Image baselines, and region-aware download scoping.
3. [**Workflows & Validation**](docs/03-workflows.md) – Building workflow step sequences, configuring `ping`/`wait` parameters, and grouping validation checks into templates.
4. [**Device Synchronization**](docs/04-device-sync.md) – Running sync jobs (auto-update vs. manual review), polling job status, and approving diffs via API.
5. [**Upgrades & Job Logs**](docs/05-device-upgrades.md) – Queuing upgrade jobs, execution modes (`mock`/`dry_run`/`execute`), dry-run pipeline analysis, and tailing live logs.

---

## Data Model Relationships

The following entity-relationship diagram illustrates how the plugin's data models interact with each other and with core NetBox models:

```mermaid
erDiagram
    %% Core NetBox DCIM Models
    dcim_Platform {
        string name
    }
    dcim_DeviceType {
        string model
    }
    dcim_Device {
        string name
    }
    dcim_Region {
        string name
    }
    dcim_Site {
        string name
    }

    %% SWIM Plugin Key Management Models
    HardwareGroup {
        string name
        string deployment_mode
        string connection_priority
        int min_version
        int max_version
        int workflow_template_id FK
    }

    SoftwareImage {
        string image_name
        string image_file_name
        string version
        string image_type
        string deployment_mode
        int file_size_bytes
        string hash_md5
        int file_server_id FK
        int platform_id FK
    }

    GoldenImage {
        string description
        string deployment_mode
        int device_type_id FK
        int hardware_group_id FK
        int image_id FK
    }

    FileServer {
        string name
        string protocol
        string ip_address
        string base_path
    }

    %% Distribution & Compliance Models
    DeviceCompliance {
        string compliance_status
        string state_reason
        string last_verified
        int device_id FK
        int current_image_id FK
        int golden_image_id FK
        int update_job_id FK
    }

    SyncJob {
        string status
        string start_time
        string end_time
    }

    DeviceSyncRecord {
        string status
        string expected_version
        string actual_version
        int device_id FK
        int sync_job_id FK
    }

    %% Automation & Workflows Models
    WorkflowTemplate {
        string name
        boolean is_active
    }

    WorkflowStep {
        string name
        string action_type
        int sequence
        int template_id FK
    }

    CheckTemplate {
        string name
    }

    ValidationCheck {
        string name
        string platform
        string command
        string json_path
        string operator
        string expected_value
    }

    UpgradeJob {
        string status
        string scheduled_time
        int device_id FK
        int target_image_id FK
        int template_id FK
    }

    JobLog {
        string action_type
        string result
        string timestamp
        int job_id FK
    }

    %% Hardware Group Links
    dcim_Platform }o--o{ HardwareGroup : "platforms"
    dcim_DeviceType }o--o{ HardwareGroup : "device_types"
    WorkflowTemplate ||--o{ HardwareGroup : "default automated template"

    %% File Server Scopes
    dcim_Region }o--o{ FileServer : "available in"
    dcim_Site }o--o{ FileServer : "available in"
    dcim_Device }o--o{ FileServer : "explicit devices"

    %% Image Matrix Links
    dcim_Platform ||--o{ SoftwareImage : "platform format"
    HardwareGroup }o--o{ SoftwareImage : "applicable groups"
    dcim_DeviceType }o--o{ SoftwareImage : "supported hardware"
    FileServer ||--o{ SoftwareImage : "hosted on"

    %% Golden Base Lines
    SoftwareImage ||--o{ GoldenImage : "is designated baseline"
    dcim_DeviceType ||--o{ GoldenImage : "for specific type"
    HardwareGroup ||--o{ GoldenImage : "for generic group"

    %% Device State & Job execution
    dcim_Device ||--o| DeviceCompliance : "status lookup"
    SoftwareImage ||--o{ DeviceCompliance : "actual reported"
    GoldenImage ||--o{ DeviceCompliance : "target baseline"

    %% Automation Chains
    WorkflowTemplate ||--|{ WorkflowStep : "contains steps"
    UpgradeJob ||--o{ JobLog : "generates logs"
    WorkflowTemplate ||--o{ UpgradeJob : "executed via"
    dcim_Device ||--o{ UpgradeJob : "targeted at"
    SoftwareImage ||--o{ UpgradeJob : "pushing image"

    %% Validation Mappings
    CheckTemplate }o--o{ ValidationCheck : "groups generic tests"
    WorkflowStep }o--o{ ValidationCheck : "runs single checks"
    WorkflowStep }o--o{ CheckTemplate : "runs template suites"

    %% Synchronisation
    SyncJob ||--|{ DeviceSyncRecord : "manages records"
    dcim_Device ||--o{ DeviceSyncRecord : "audited via"

```
