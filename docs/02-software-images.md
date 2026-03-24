# Software Images, Golden Images & File Servers

These three models manage the artifact layer of the plugin—describing *what* files exist, *where* they're hosted, and *which* hardware should run them.

## 1. File Servers
A `FileServer` must be set up before images can reference a download location. Instead of storing firmware blobs in the database, SWIM points to external file servers.
- **Protocol**: `HTTP`, `SCP`, or `FTP`. This tells the device how to fetch the file (e.g. `copy http://...` on Cisco IOS).
- **IP Address & Base Path**: Host and directory where images are stored.
- **Region/Site Scoping**: Assigning a File Server to a NetBox `Region` or `Site` causes the engine to prefer that server for devices in that area. This avoids sending large files across WAN links unnecessarily.

### File Server API Operations
- **Endpoint:** `/api/plugins/swim/file-servers/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

**Creating an HTTP File Server scoped to a specific Site:**
```python
import requests
HEADERS = {"Authorization": "Token <TOKEN>", "Content-Type": "application/json"}
# (Assuming Site 'NYC-Datacenter' has PK=12)
payload = {
    "name": "NYC HTTP Artifacts",
    "protocol": "http",
    "ip_address": "10.0.0.50",
    "base_path": "/images/cisco/",
    "sites": [12] 
}
requests.post("http://<netbox_url>/api/plugins/swim/file-servers/", json=payload, headers=HEADERS)
```

---

## 2. Software Images
Represents the actual OS binary that gets pushed to devices.
- **Image Type**: Boot, System, FPGA, etc.
- **File Server & Platform**: Which server hosts this file, and which platform it targets (e.g. `cisco_ios`).
- **File Size Bytes & MD5 Hash**: Used by the distribution step to verify available flash space and validate file integrity after transfer.

### Software Image API Operations
- **Endpoint:** `/api/plugins/swim/images/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

**Creating a Software Image Record:**
```python
requests.post("http://<netbox_url>/api/plugins/swim/images/", headers=HEADERS, json={
    "image_name": "Cisco IOS XE 17.6.4",
    "image_file_name": "cat9k_iosxe.17.06.04.SPA.bin",
    "version": "17.06.04",
    "image_type": "system",
    "file_size_bytes": 1058000213,
    "hash_md5": "abc123hashmd5...",
    "file_server": 1,  # The File Server PK
    "platform": 2      # The NetBox Platform PK
})
```

---

## 3. Golden Images
A `GoldenImage` links a `SoftwareImage` as the required baseline for either a specific `DeviceType` or a broader `HardwareGroup`.
This is the table the compliance engine reads to determine if a device is up-to-date or needs an upgrade.

### Golden Image API Operations
- **Endpoint:** `/api/plugins/swim/golden-images/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

**Setting a baseline image requirement:**
```python
requests.post("http://<netbox_url>/api/plugins/swim/golden-images/", headers=HEADERS, json={
    "description": "Target Catalyst Baseline FY25",
    "image": 14,             # SoftwareImage PK
    "hardware_group": 2,     # Apply to entire Hardware Group
    "deployment_mode": "in-service"
})
```
