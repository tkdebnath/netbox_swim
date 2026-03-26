#!/usr/bin/env python3
"""
Add a new device to NetBox with primary IP, platform, site, role.

Usage:
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=your-token
    python 01_add_device.py
"""

import os
import re
import requests

BASE_URL = os.environ.get("NETBOX_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN", "")
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}


def slugify(text):
    """Convert any text to a URL-safe slug. e.g. 'Catalyst 9300-48P' -> 'catalyst-9300-48p'"""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def add_device(name, device_type, site, platform, role,
               ip_address, serial="", software_version="", deployment_mode="campus"):
    """Add a device and assign a primary IP. Pass names or slugs — slugs are auto-generated."""

    # 1. Create the device
    device_payload = {
        "name": name,
        "device_type": {"slug": slugify(device_type)},
        "site": {"slug": slugify(site)},
        "platform": {"slug": slugify(platform)},
        "role": {"slug": slugify(role)},
        "status": "active",
        "serial": serial,
        "custom_fields": {
            "software_version": software_version,
            "deployment_mode": deployment_mode,
        }
    }

    r = requests.post(f"{BASE_URL}/api/dcim/devices/", headers=HEADERS, json=device_payload)
    if r.status_code not in (200, 201):
        print(f"FAIL creating device: {r.status_code} — {r.text[:200]}")
        return None

    device = r.json()
    device_id = device["id"]
    print(f"OK   Device '{name}' created (id={device_id})")

    # 2. Create an IP address
    if ip_address:
        ip_payload = {
            "address": ip_address,
            "assigned_object_type": "dcim.interface",
            "description": f"Primary IP for {name}",
        }

        # First create a management interface
        intf_payload = {
            "device": device_id,
            "name": "GigabitEthernet0/0",
            "type": "1000base-t",
        }
        r_intf = requests.post(f"{BASE_URL}/api/dcim/interfaces/", headers=HEADERS, json=intf_payload)
        if r_intf.status_code in (200, 201):
            intf_id = r_intf.json()["id"]
            print(f"OK   Interface created (id={intf_id})")

            # Assign IP to that interface
            ip_payload["assigned_object_type"] = "dcim.interface"
            ip_payload["assigned_object_id"] = intf_id
            r_ip = requests.post(f"{BASE_URL}/api/ipam/ip-addresses/", headers=HEADERS, json=ip_payload)
            if r_ip.status_code in (200, 201):
                ip_id = r_ip.json()["id"]
                print(f"OK   IP {ip_address} created (id={ip_id})")

                # Set as primary IP on device
                r_patch = requests.patch(
                    f"{BASE_URL}/api/dcim/devices/{device_id}/",
                    headers=HEADERS,
                    json={"primary_ip4": ip_id}
                )
                if r_patch.status_code == 200:
                    print(f"OK   Set {ip_address} as primary IP")
                else:
                    print(f"FAIL setting primary IP: {r_patch.text[:150]}")
            else:
                print(f"FAIL creating IP: {r_ip.text[:150]}")
        else:
            print(f"FAIL creating interface: {r_intf.text[:150]}")

    return device_id


# ============================================================
# Example: Add a device
# ============================================================
if __name__ == "__main__":
    # Just pass friendly names — slugs are auto-generated
    add_device(
        name="LAB-SW-01",
        device_type="Catalyst 9300-48P",
        site="San Jose HQ",
        platform="Cisco IOS-XE",
        role="Campus Core",
        ip_address="10.1.1.100/24",
        serial="FCW2401X001",
        software_version="17.06.05",
        deployment_mode="campus",
    )
