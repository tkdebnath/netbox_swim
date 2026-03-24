# Installation & Configuration

This guide covers installing the SWIM plugin on both Docker and bare-metal NetBox deployments, configuring device credentials, and setting up background workers.

## Prerequisites
- NetBox **v4.0+** (tested on v4.5)
- Python **3.10+**
- Redis (used for background job queuing via `django-rq`)
- SSH access from the NetBox host/container to managed devices

---

## Installation: Docker (netbox-docker)

This is the recommended method if you're running the [netbox-community/netbox-docker](https://github.com/netbox-community/netbox-docker) stack.

### Step 1 — Add the plugin to `plugin_requirements.txt`
Create (or edit) `plugin_requirements.txt` in the root of your `netbox-docker` directory:

**From PyPI (when published):**
```
netbox-swim
```

**From a Git repository:**
```
netbox-swim @ git+https://github.com/<your-org>/netbox-swim.git
```

**From a local path (bind-mounted into the container):**
```
-e /opt/netbox/netbox-swim
```

### Step 2 — Create or update `Dockerfile-Plugins`
```dockerfile
FROM netboxcommunity/netbox:latest

COPY ./plugin_requirements.txt /opt/netbox/
RUN /usr/local/bin/uv pip install --no-cache -r /opt/netbox/plugin_requirements.txt

# Collect static files for the plugin
COPY configuration/plugins.py /etc/netbox/config/plugins.py
RUN SECRET_KEY="dummy-key-for-collectstatic" \
    /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py collectstatic --no-input
```

> **Note:** The netbox-docker image ships with `uv` as the package manager. Use `/usr/local/bin/uv pip install` instead of plain `pip install`.

### Step 3 — Create or update `docker-compose.override.yml`
```yaml
services:
  netbox: &netbox
    image: netbox:latest-plugins
    pull_policy: never
    build:
      context: .
      dockerfile: Dockerfile-Plugins
    env_file:
      - env/netbox.env
      - env/swim.env          # SWIM credentials (see below)
  netbox-worker:
    image: netbox:latest-plugins
    pull_policy: never
    env_file:
      - env/netbox.env
      - env/swim.env
```

### Step 4 — Enable the plugin
Add to `configuration/plugins.py`:
```python
PLUGINS = ["netbox_swim"]
```

### Step 5 — Build and start
```bash
docker compose build --no-cache
docker compose up -d
```

Migrations run automatically on container startup. To verify:
```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py migrate --check
```

### Upgrading the Plugin (Docker)
To pull a newer version of the plugin:
1. Update the version pin in `plugin_requirements.txt` (or leave unpinned to get latest).
2. Rebuild:
```bash
docker compose build --no-cache
docker compose down && docker compose up -d
```

---

## Installation: Bare Metal

### Step 1 — Install the package
Activate the NetBox virtual environment first:
```bash
source /opt/netbox/venv/bin/activate
```

**From PyPI:**
```bash
pip install netbox-swim
```

**From a Git repository:**
```bash
pip install git+https://github.com/<your-org>/netbox-swim.git
```

**From local source (editable/development):**
```bash
cd /path/to/netbox-swim
pip install -e .
```

> **Tip:** To ensure the plugin persists across NetBox upgrades, add it to `/opt/netbox/local_requirements.txt`:
> ```
> netbox-swim
> ```

### Step 2 — Enable the plugin
Edit `/opt/netbox/netbox/netbox/configuration.py` (or the `plugins.py` include if your deployment uses split config):
```python
PLUGINS = ["netbox_swim"]
```

### Step 3 — Run migrations and collect static files
```bash
cd /opt/netbox/netbox
python3 manage.py migrate
python3 manage.py collectstatic --no-input
```

### Step 4 — Restart services
```bash
sudo systemctl restart netbox netbox-rq
```

### Upgrading the Plugin (Bare Metal)
```bash
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-swim
cd /opt/netbox/netbox
python3 manage.py migrate
python3 manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

---

## Device Credentials

SWIM reads SSH credentials from **environment variables**, not from the NetBox database. This keeps passwords out of the Django ORM entirely.

### Default Credentials
Set these three environment variables on the NetBox host (or in your Docker env file):

| Variable          | Purpose                                  |
|-------------------|------------------------------------------|
| `SWIM_USERNAME`   | SSH username for device connections      |
| `SWIM_PASSWORD`   | SSH password                             |
| `SWIM_SECRET`     | Enable/privilege secret (Cisco `enable`) |

**Example `env/swim.env` (Docker):**
```bash
SWIM_USERNAME=netops
SWIM_PASSWORD=s3cur3Pa$$
SWIM_SECRET=en4bl3S3cret
```

**Bare metal — export in your shell or add to `/etc/default/netbox`:**
```bash
export SWIM_USERNAME=netops
export SWIM_PASSWORD=s3cur3Pa$$
export SWIM_SECRET=en4bl3S3cret
```

### Per-Site / Per-Group Credential Profiles

If different device groups use different credentials, you can define **credential profiles** via NetBox Config Contexts. This lets you assign different SSH credentials per site, region, or device role without changing the plugin code.

**Step 1:** Define a Config Context in NetBox (UI or API) and assign it to the relevant scope (site, role, etc.):
```json
{
    "swim": {
        "credential_profile": "site_b_creds"
    }
}
```

**Step 2:** Set the matching environment variables using the profile name as a prefix (uppercased):
```bash
SITE_B_CREDS_USERNAME=site_b_admin
SITE_B_CREDS_PASSWORD=site_b_password
SITE_B_CREDS_SECRET=site_b_enable
```

**How it works:** When a sync or upgrade job runs against a device, the plugin checks the device's Config Context for `swim.credential_profile`. If found, it reads `{PROFILE}_USERNAME`, `{PROFILE}_PASSWORD`, and `{PROFILE}_SECRET` from the environment. If no profile is set, it falls back to the default `SWIM_USERNAME` / `SWIM_PASSWORD` / `SWIM_SECRET`.

### Credential Resolution Order
1. Config Context → `swim.credential_profile` → `{PROFILE}_USERNAME` etc.
2. Fallback → `SWIM_USERNAME` / `SWIM_PASSWORD` / `SWIM_SECRET`

---

## Platform Mapping

The plugin translates NetBox platform slugs (e.g. `cisco-ios`, `cisco_nxos`, `arista-eos`) into the correct driver names for each connection library. This mapping lives in `netbox_swim/constants.py` under `PLATFORM_MAPPINGS`.

**Supported platforms out of the box:**

| NetBox Slug(s)                     | Scrapli        | Netmiko        | pyATS/Unicon |
|------------------------------------|----------------|----------------|--------------|
| `cisco-ios`, `ios`                 | `cisco_iosxe`  | `cisco_ios`    | `ios`        |
| `cisco-ios-xe`, `cisco_iosxe`      | `cisco_iosxe`  | `cisco_ios`    | `iosxe`      |
| `cisco-nx-os`, `cisco_nxos`, `nxos`| `cisco_nxos`   | `cisco_nxos`   | `nxos`       |
| `juniper-junos`, `junos`           | `juniper_junos`| `juniper_junos`| `junos`      |
| `arista-eos`, `eos`                | `arista_eos`   | `arista_eos`   | `eos`        |
| `paloalto-panos`, `panos`          | `paloalto_panos`| `paloalto_panos`| `panos`    |

To add a new platform, add an entry to `PLATFORM_MAPPINGS` in `constants.py` and restart NetBox.

---

## Custom Fields (Auto-Provisioned)

On startup, the plugin automatically creates these custom fields on `dcim.Device` (grouped under "SWIM Derived Data"):

| Field Name                  | Type     | Description                         |
|-----------------------------|----------|-------------------------------------|
| `deployment_mode`           | Select   | Campus / SD-WAN / Universal         |
| `software_version`          | Text     | Running firmware version            |
| `tacacs_source_interface`   | Text     | Discovered TACACS+ source interface |
| `tacacs_source_ip`          | Text     | Discovered TACACS+ source IP        |
| `vrf`                       | Text     | Discovered VRF instance             |
| `swim_last_sync_status`     | Select   | Success / Error / Pending           |
| `swim_last_successful_sync` | Datetime | Last successful sync timestamp      |

To add or remove custom fields, edit the `SWIM_CUSTOM_FIELDS` list in `constants.py` and restart NetBox.

---

## Connection Libraries

The plugin supports three SSH connection backends. You select which one to use when triggering a sync or upgrade job (via the UI or API).

| Library    | Best For                                      | Notes                                |
|------------|-----------------------------------------------|--------------------------------------|
| **Scrapli** | Fast, lightweight connections                 | Default. SSH transport via `system`. |
| **Netmiko** | Broad vendor support, well-tested             | Good fallback option.                |
| **pyATS/Unicon** | Cisco-only, advanced features (pyATS testbed) | Requires `pyats`, `unicon`, `genie`. |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Sync jobs stay "pending" forever | RQ worker not running | Restart the `netbox-worker` container or `netbox-rq` service |
| SSH timeout errors | No network path from NetBox to device | Check routing, firewall rules, and that `primary_ip` is set on the device |
| "Device lacks a Primary IP" | Device has no Primary IP assigned | Set a Primary IP on the device in NetBox |
| Custom fields not appearing | Plugin `ready()` failed silently | Check NetBox logs; run `python manage.py migrate` |
| Wrong platform driver selected | Platform slug doesn't match `PLATFORM_MAPPINGS` | Check the device's Platform slug in NetBox against `constants.py` |
| Plugin not loading after Docker rebuild | Stale image cache | Run `docker compose build --no-cache` |
| `ModuleNotFoundError: netbox_swim` | Plugin not installed in the venv | Verify with `pip list | grep swim` inside the container/venv |
