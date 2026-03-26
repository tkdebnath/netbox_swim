#!/usr/bin/env python3
"""
SWIM Plugin — Seed Data Loader
Loads all numbered JSON files into NetBox via REST API.
Skips objects that already exist. Run in order.

Usage:
    python load_seed_data.py
    
Set these before running:
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=your-api-token-here
"""

import os
import json
import requests

# --- Config ---
BASE_URL = os.environ.get("NETBOX_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN", "")
HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json",
}

if not TOKEN:
    print("ERROR: Set NETBOX_TOKEN environment variable first.")
    exit(1)


def get_all(endpoint):
    """Get all objects from an endpoint."""
    url = f"{BASE_URL}{endpoint}?limit=1000"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json().get("results", [])


def find_by_field(endpoint, field, value):
    """Check if an object already exists."""
    for obj in get_all(endpoint):
        if str(obj.get(field, "")).lower() == str(value).lower():
            return obj
    return None


def create_if_missing(endpoint, payload, match_field, label=""):
    """POST to endpoint only if object doesn't exist. Returns ID."""
    match_value = payload.get(match_field, "")
    existing = find_by_field(endpoint, match_field, match_value)

    if existing:
        print(f"  SKIP  {label or match_value} (already exists, id={existing['id']})")
        return existing["id"]

    r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        new_id = r.json()["id"]
        print(f"  OK    {label or match_value} (created, id={new_id})")
        return new_id
    else:
        print(f"  FAIL  {label or match_value} — {r.status_code}: {r.text[:200]}")
        return None


def resolve_id(endpoint, field, value):
    """Look up an object ID by field value."""
    obj = find_by_field(endpoint, field, value)
    return obj["id"] if obj else None


# ============================================================
# STEP LOADERS
# ============================================================

def load_01(data):
    print("\n--- Step 01: Manufacturers & Platforms ---")
    for m in data.get("manufacturers", []):
        create_if_missing("/api/dcim/manufacturers/", m, "slug")

    for p in data.get("platforms", []):
        mfr = p.get("manufacturer", {})
        if isinstance(mfr, dict):
            p["manufacturer"] = resolve_id("/api/dcim/manufacturers/", "slug", mfr["slug"])
        create_if_missing("/api/dcim/platforms/", p, "slug")


def load_02(data):
    print("\n--- Step 02: Device Types ---")
    for dt in data.get("data", []):
        mfr = dt.get("manufacturer", {})
        if isinstance(mfr, dict):
            dt["manufacturer"] = resolve_id("/api/dcim/manufacturers/", "slug", mfr["slug"])
        create_if_missing("/api/dcim/device-types/", dt, "slug")


def load_03(data):
    print("\n--- Step 03: Regions & Sites ---")
    for r in data.get("regions", []):
        create_if_missing("/api/dcim/regions/", r, "slug")

    for s in data.get("sites", []):
        region = s.get("region", {})
        if isinstance(region, dict):
            s["region"] = resolve_id("/api/dcim/regions/", "slug", region["slug"])
        create_if_missing("/api/dcim/sites/", s, "slug")


def load_04(data):
    print("\n--- Step 04: Device Roles ---")
    for role in data.get("data", []):
        create_if_missing("/api/dcim/device-roles/", role, "slug")


def load_05(data):
    print("\n--- Step 05: Devices ---")
    for dev in data.get("data", []):
        for field, endpoint, key in [
            ("device_type", "/api/dcim/device-types/", "slug"),
            ("role", "/api/dcim/device-roles/", "slug"),
            ("site", "/api/dcim/sites/", "slug"),
            ("platform", "/api/dcim/platforms/", "slug"),
        ]:
            ref = dev.get(field, {})
            if isinstance(ref, dict):
                dev[field] = resolve_id(endpoint, key, ref[key])
        create_if_missing("/api/dcim/devices/", dev, "name")


def load_06(data):
    print("\n--- Step 06: File Servers ---")
    for fs in data.get("data", []):
        create_if_missing("/api/plugins/swim/file-servers/", fs, "name")


def load_07(data):
    print("\n--- Step 07: Validation Checks ---")
    for vc in data.get("data", []):
        create_if_missing("/api/plugins/swim/validation-checks/", vc, "name")


def load_08(data):
    print("\n--- Step 08: Check Templates ---")
    for ct in data.get("data", []):
        # Resolve check name placeholders to IDs
        resolved = []
        for ref in ct.get("checks", []):
            if isinstance(ref, str) and ref.startswith("__ID_"):
                name = ref.replace("__ID_", "").replace("__", "").replace("_", " ").title()
                cid = resolve_id("/api/plugins/swim/validation-checks/", "name", name)
                if cid:
                    resolved.append(cid)
            elif isinstance(ref, int):
                resolved.append(ref)
        ct["checks"] = resolved
        create_if_missing("/api/plugins/swim/check-templates/", ct, "name")


def load_09(data):
    print("\n--- Step 09: Workflow Templates ---")
    for wt in data.get("data", []):
        create_if_missing("/api/plugins/swim/workflow-templates/", wt, "name")


def load_10(data):
    print("\n--- Step 10: Workflow Steps ---")
    TEMPLATE_NAMES = {
        "__TEMPLATE_ID_CAMPUS__": "Standard Campus Upgrade",
        "__TEMPLATE_ID_SDWAN__":  "SD-WAN Edge Upgrade",
        "__TEMPLATE_ID_DC__":     "Data Center Rolling Upgrade",
        "__TEMPLATE_ID_HOTFIX__": "Emergency Hotfix (No Checks)",
    }
    for ws in data.get("data", []):
        tmpl = ws.get("template")
        if isinstance(tmpl, str) and tmpl in TEMPLATE_NAMES:
            ws["template"] = resolve_id("/api/plugins/swim/workflow-templates/", "name", TEMPLATE_NAMES[tmpl])

        # Check if step already exists (match template + order)
        existing_steps = get_all("/api/plugins/swim/workflow-steps/")
        already = any(s["template"]["id"] == ws["template"] and s["order"] == ws["order"]
                      for s in existing_steps if isinstance(s.get("template"), dict))
        if already:
            print(f"  SKIP  Step order={ws['order']} (already exists)")
            continue

        r = requests.post(f"{BASE_URL}/api/plugins/swim/workflow-steps/", headers=HEADERS, json=ws)
        if r.status_code in (200, 201):
            print(f"  OK    Step order={ws['order']} action={ws['action_type']}")
        else:
            print(f"  FAIL  Step order={ws['order']} — {r.status_code}: {r.text[:150]}")


def load_11(data):
    print("\n--- Step 11: Hardware Groups ---")
    TEMPLATE_NAMES = {
        "__TEMPLATE_ID_CAMPUS__": "Standard Campus Upgrade",
        "__TEMPLATE_ID_SDWAN__":  "SD-WAN Edge Upgrade",
        "__TEMPLATE_ID_DC__":     "Data Center Rolling Upgrade",
        "__TEMPLATE_ID_HOTFIX__": "Emergency Hotfix (No Checks)",
    }
    for hg in data.get("data", []):
        hg = {k: v for k, v in hg.items() if not k.startswith("_")}
        wt = hg.get("workflow_template")
        if isinstance(wt, str) and wt in TEMPLATE_NAMES:
            hg["workflow_template"] = resolve_id("/api/plugins/swim/workflow-templates/", "name", TEMPLATE_NAMES[wt])
        create_if_missing("/api/plugins/swim/hardware-groups/", hg, "slug")


def load_12(data):
    print("\n--- Step 12: Software Images ---")
    PLATFORMS = {
        "__PLATFORM_ID_IOSXE__": "cisco-ios-xe",
        "__PLATFORM_ID_IOS__":   "cisco-ios",
        "__PLATFORM_ID_NXOS__":  "cisco-nx-os",
        "__PLATFORM_ID_IOSXR__": "cisco-ios-xr",
    }
    FILE_SERVERS = {
        "__FILESERVER_ID_SJ_HTTP__": "SJ-HTTP-SRV",
        "__FILESERVER_ID_SJ_TFTP__": "SJ-TFTP-SRV",
        "__FILESERVER_ID_GLOBAL__":  "Global-HTTPS-Repo",
        "__FILESERVER_ID_NY_SCP__":  "NY-SCP-SRV",
    }
    for img in data.get("data", []):
        img = {k: v for k, v in img.items() if not k.startswith("_")}
        p = img.get("platform")
        if isinstance(p, str) and p in PLATFORMS:
            img["platform"] = resolve_id("/api/dcim/platforms/", "slug", PLATFORMS[p])
        fs = img.get("file_server")
        if isinstance(fs, str) and fs in FILE_SERVERS:
            img["file_server"] = resolve_id("/api/plugins/swim/file-servers/", "name", FILE_SERVERS[fs])
        create_if_missing("/api/plugins/swim/software-images/", img, "image_name")


def load_13(data):
    print("\n--- Step 13: Golden Images ---")
    IMAGES = {
        "__IMAGE_ID_C9300_CAMPUS__": "Cat9k-IOS-XE-17.09.05",
        "__IMAGE_ID_C9200_CAMPUS__": "Cat9200-IOS-XE-17.09.05",
        "__IMAGE_ID_SDWAN__":        "Cat9k-SDWAN-17.09.05",
        "__IMAGE_ID_NXOS__":         "NX-OS-10.3(2)F",
    }
    for gi in data.get("data", []):
        gi = {k: v for k, v in gi.items() if not k.startswith("_")}
        img = gi.get("image")
        if isinstance(img, str) and img in IMAGES:
            gi["image"] = resolve_id("/api/plugins/swim/software-images/", "image_name", IMAGES[img])
        if not gi.get("image"):
            print(f"  FAIL  Could not resolve image reference")
            continue

        r = requests.post(f"{BASE_URL}/api/plugins/swim/golden-images/", headers=HEADERS, json=gi)
        if r.status_code in (200, 201):
            print(f"  OK    Golden Image created (mode={gi.get('deployment_mode')})")
        elif "already exists" in r.text.lower() or "unique" in r.text.lower():
            print(f"  SKIP  Golden Image already exists (mode={gi.get('deployment_mode')})")
        else:
            print(f"  FAIL  {r.status_code}: {r.text[:150]}")


# ============================================================
# MAIN
# ============================================================

LOADERS = {
    "01": load_01, "02": load_02, "03": load_03, "04": load_04,
    "05": load_05, "06": load_06, "07": load_07, "08": load_08,
    "09": load_09, "10": load_10, "11": load_11, "12": load_12,
    "13": load_13,
}

if __name__ == "__main__":
    print(f"Loading seed data into {BASE_URL} ...")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    for step_num in sorted(LOADERS.keys()):
        # Find the JSON file for this step
        files = [f for f in os.listdir(script_dir) if f.startswith(f"{step_num}_") and f.endswith(".json")]
        if not files:
            continue

        filepath = os.path.join(script_dir, files[0])
        with open(filepath) as f:
            data = json.load(f)

        LOADERS[step_num](data)

    print("\nDone!")
