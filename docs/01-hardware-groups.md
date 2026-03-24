# Managing Hardware Groups

The **Hardware Group** is the foundational model for the SWIM plugin. It lets you group NetBox `Platform` and `Device Type` objects into a single logical pool. For example, you could create a "Global Catalyst 9300" group that covers all C9300-24P and C9300-48P variants under one upgrade policy.

## Field Functionality
- **Platforms & Device Types**: Links to standard NetBox objects. Assigning a `cisco_ios` Platform here tells the engine which connection protocols to use for devices in this group.
- **Workflow Template**: The default upgrade pipeline that runs when a remediation job targets this group.
- **Connection Priority**: SSH library fallback order (e.g. `scrapli,netmiko,unicon`).
- **Min/Max Version Restrictions**: Integer parameters that gate whether a device qualifies for upgrades.

---

## API Endpoints

**URL Base:** `/api/plugins/swim/hardware-groups/`
**Supported Methods:** `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

### 1. Creating a Hardware Group (POST)
```python
import requests
HEADERS = {"Authorization": "Token <YOUR_TOKEN>", "Content-Type": "application/json"}

payload = {
    "name": "Global Cisco C9300s",
    "slug": "c9300-global",
    "deployment_mode": "in-service",
    "connection_priority": "cli,netconf",
    "min_version": 17,
    "max_version": 20
}
res = requests.post("http://<netbox_url>/api/plugins/swim/hardware-groups/", json=payload, headers=HEADERS)
print(res.json()['id'])  # Returns the new group's primary key
```

### 2. Attaching Device Types & Platforms (PATCH)
NetBox M2M fields are set as arrays. A PATCH replaces the entire list—include all PKs you want assigned.
```python
hwg_id = 5

# Set the assigned Device Types and Platforms by their NetBox PKs
patch_payload = {
    "device_types": [14, 15, 120],
    "platforms": [1, 2]
}
requests.patch(f"http://<netbox_url>/api/plugins/swim/hardware-groups/{hwg_id}/", json=patch_payload, headers=HEADERS)
```
