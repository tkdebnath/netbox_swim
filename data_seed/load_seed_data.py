#!/usr/bin/env python3
"""
SWIM Plugin — Idempotent Seed Data Loader

Iterates through the numbered JSON files in this directory and creates
objects via the NetBox REST API.  If an object already exists (matched
by its natural key — name, slug, or unique composite), it is **skipped**
and the existing ID is captured for downstream cross-references.

Usage:
    python load_seed_data.py --url http://localhost:8000 --token <your-token>

Environment variables (fallback):
    NETBOX_URL   — base URL  (default: http://localhost:8000)
    NETBOX_TOKEN — API token
"""

import os
import sys
import json
import argparse
import requests
from urllib.parse import urljoin

# ──────────────────────────────────────────────────────────────
# Colour helpers for terminal output
# ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def skip(msg):  print(f"  {YELLOW}⏭{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {CYAN}ℹ{RESET} {msg}")

# ──────────────────────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────────────────────
class NetBoxAPI:
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })
        # Verify connectivity
        r = self.session.get(f"{self.base}/api/status/")
        if r.status_code != 200:
            sys.exit(f"Cannot reach NetBox at {self.base} (HTTP {r.status_code})")

    def get_list(self, endpoint, params=None):
        """Return ALL objects from a paginated list endpoint."""
        url = f"{self.base}{endpoint}"
        results = []
        while url:
            r = self.session.get(url, params=params)
            r.raise_for_status()
            body = r.json()
            results.extend(body.get("results", []))
            url = body.get("next")
            params = None        # next URL already has query string
        return results

    def post(self, endpoint, payload):
        url = f"{self.base}{endpoint}"
        r = self.session.post(url, json=payload)
        return r

    def patch(self, endpoint, obj_id, payload):
        url = f"{self.base}{endpoint}{obj_id}/"
        r = self.session.patch(url, json=payload)
        return r


# ──────────────────────────────────────────────────────────────
# Registry: stores created/found IDs for cross-referencing
# ──────────────────────────────────────────────────────────────
ID_REGISTRY = {}   # "type:natural_key" → id

def reg_key(obj_type, natural_key):
    return f"{obj_type}:{natural_key}"

def register(obj_type, natural_key, obj_id):
    ID_REGISTRY[reg_key(obj_type, natural_key)] = obj_id

def lookup(obj_type, natural_key):
    return ID_REGISTRY.get(reg_key(obj_type, natural_key))


# ──────────────────────────────────────────────────────────────
# Generic "find or create" with natural-key matching
# ──────────────────────────────────────────────────────────────
def find_existing(api, endpoint, match_fields, payload):
    """
    Search the endpoint for an object matching the given fields.
    Returns the existing object dict or None.
    """
    params = {}
    for field in match_fields:
        val = payload.get(field)
        if val is not None:
            params[field] = val
    if not params:
        return None
    results = api.get_list(endpoint, params=params)
    # Exact match
    for obj in results:
        if all(str(obj.get(f, "")).lower() == str(params[f]).lower() for f in params):
            return obj
    return None


def safe_create(api, endpoint, payload, match_fields, label="object", obj_type="generic"):
    """
    POST payload to endpoint.  If an object already exists (matched by
    match_fields), skip and return the existing ID.
    """
    existing = find_existing(api, endpoint, match_fields, payload)
    if existing:
        obj_id = existing["id"]
        natural = payload.get(match_fields[0], "?")
        skip(f"{label} '{natural}' already exists (id={obj_id})")
        register(obj_type, natural, obj_id)
        return obj_id, False

    r = api.post(endpoint, payload)
    if r.status_code in (200, 201):
        obj_id = r.json()["id"]
        natural = payload.get(match_fields[0], "?")
        ok(f"Created {label} '{natural}' (id={obj_id})")
        register(obj_type, natural, obj_id)
        return obj_id, True
    else:
        natural = payload.get(match_fields[0], "?")
        # Check if error means "already exists"
        err_text = r.text.lower()
        if "already exists" in err_text or "unique" in err_text or "must be unique" in err_text:
            skip(f"{label} '{natural}' already exists (API constraint)")
            # Try to fetch it
            existing = find_existing(api, endpoint, match_fields, payload)
            if existing:
                register(obj_type, natural, existing["id"])
                return existing["id"], False
            return None, False
        else:
            fail(f"Failed to create {label} '{natural}': {r.status_code} — {r.text[:300]}")
            return None, False


# ──────────────────────────────────────────────────────────────
# Step loaders
# ──────────────────────────────────────────────────────────────

def load_01_manufacturers_platforms(api, data):
    """Manufacturers + Platforms"""
    for m in data.get("manufacturers", []):
        safe_create(api, "/api/dcim/manufacturers/", m, ["slug"], "Manufacturer", "manufacturer")

    for p in data.get("platforms", []):
        # Resolve manufacturer ref
        mfr_slug = p.get("manufacturer", {}).get("slug")
        if mfr_slug:
            mfr_id = lookup("manufacturer", mfr_slug)
            if not mfr_id:
                # Try slug-based lookup
                mfr_id = lookup("manufacturer", mfr_slug)
            p["manufacturer"] = mfr_id or p["manufacturer"]
        safe_create(api, "/api/dcim/platforms/", p, ["slug"], "Platform", "platform")


def load_02_device_types(api, data):
    """Device Types"""
    for dt in data.get("data", []):
        mfr = dt.get("manufacturer", {})
        if isinstance(mfr, dict):
            mfr_slug = mfr.get("slug")
            mfr_id = lookup("manufacturer", mfr_slug)
            if mfr_id:
                dt["manufacturer"] = mfr_id
        safe_create(api, "/api/dcim/device-types/", dt, ["slug"], "DeviceType", "device_type")


def load_03_sites_regions(api, data):
    """Regions + Sites"""
    for r in data.get("regions", []):
        safe_create(api, "/api/dcim/regions/", r, ["slug"], "Region", "region")

    for s in data.get("sites", []):
        region_ref = s.get("region", {})
        if isinstance(region_ref, dict):
            r_slug = region_ref.get("slug")
            r_id = lookup("region", r_slug)
            if r_id:
                s["region"] = r_id
        safe_create(api, "/api/dcim/sites/", s, ["slug"], "Site", "site")


def load_04_device_roles(api, data):
    """Device Roles"""
    for role in data.get("data", []):
        safe_create(api, "/api/dcim/device-roles/", role, ["slug"], "DeviceRole", "device_role")


def load_05_devices(api, data):
    """Devices"""
    for dev in data.get("data", []):
        # Resolve FK references
        for fk_field, reg_type in [("device_type", "device_type"), ("role", "device_role"),
                                    ("site", "site"), ("platform", "platform")]:
            ref = dev.get(fk_field, {})
            if isinstance(ref, dict):
                slug = ref.get("slug")
                resolved_id = lookup(reg_type, slug)
                if resolved_id:
                    dev[fk_field] = resolved_id

        safe_create(api, "/api/dcim/devices/", dev, ["name"], "Device", "device")


def load_06_file_servers(api, data):
    """File Servers"""
    for fs in data.get("data", []):
        safe_create(api, "/api/plugins/swim/file-servers/", fs, ["name"], "FileServer", "file_server")


def load_07_validation_checks(api, data):
    """Validation Checks"""
    for vc in data.get("data", []):
        safe_create(api, "/api/plugins/swim/validation-checks/", vc, ["name"], "ValidationCheck", "validation_check")


def load_08_check_templates(api, data):
    """Check Templates — resolve check IDs from registry"""
    for ct in data.get("data", []):
        # Resolve check references
        resolved_checks = []
        raw_checks = ct.get("checks", [])
        for ref in raw_checks:
            if isinstance(ref, str) and ref.startswith("__ID_"):
                # Convert placeholder to a lookup: __ID_BGP_NEIGHBORS__ → "BGP Neighbors"
                name_guess = ref.replace("__ID_", "").replace("__", "").replace("_", " ").title()
                check_id = lookup("validation_check", name_guess)
                if check_id:
                    resolved_checks.append(check_id)
                else:
                    info(f"Could not resolve check placeholder '{ref}' → '{name_guess}'")
            elif isinstance(ref, int):
                resolved_checks.append(ref)
        ct["checks"] = resolved_checks
        safe_create(api, "/api/plugins/swim/check-templates/", ct, ["name"], "CheckTemplate", "check_template")


def load_09_workflow_templates(api, data):
    """Workflow Templates"""
    for wt in data.get("data", []):
        safe_create(api, "/api/plugins/swim/workflow-templates/", wt, ["name"], "WorkflowTemplate", "workflow_template")


def load_10_workflow_steps(api, data):
    """Workflow Steps — resolve template IDs"""
    for ws in data.get("data", []):
        tmpl_ref = ws.get("template")
        if isinstance(tmpl_ref, str) and tmpl_ref.startswith("__TEMPLATE_ID_"):
            tag = tmpl_ref.replace("__TEMPLATE_ID_", "").replace("__", "")
            name_map = {
                "CAMPUS":  "Standard Campus Upgrade",
                "SDWAN":   "SD-WAN Edge Upgrade",
                "DC":      "Data Center Rolling Upgrade",
                "HOTFIX":  "Emergency Hotfix (No Checks)",
            }
            real_name = name_map.get(tag)
            if real_name:
                tmpl_id = lookup("workflow_template", real_name)
                if tmpl_id:
                    ws["template"] = tmpl_id
                else:
                    fail(f"Cannot resolve workflow template '{real_name}'")
                    continue
            else:
                fail(f"Unknown template tag: {tag}")
                continue

        # Match on (template + order) composite
        existing = find_existing(api, "/api/plugins/swim/workflow-steps/",
                                 ["template", "order"], ws)
        if existing:
            skip(f"WorkflowStep template={ws['template']} order={ws['order']} already exists")
            continue

        r = api.post("/api/plugins/swim/workflow-steps/", ws)
        if r.status_code in (200, 201):
            ok(f"Created WorkflowStep template={ws['template']} order={ws['order']} action={ws['action_type']}")
        elif "already exists" in r.text.lower() or "unique" in r.text.lower():
            skip(f"WorkflowStep template={ws['template']} order={ws['order']} already exists")
        else:
            fail(f"WorkflowStep create failed: {r.status_code} — {r.text[:200]}")


def load_11_hardware_groups(api, data):
    """Hardware Groups — resolve workflow_template IDs"""
    name_map = {
        "__TEMPLATE_ID_CAMPUS__": "Standard Campus Upgrade",
        "__TEMPLATE_ID_SDWAN__":  "SD-WAN Edge Upgrade",
        "__TEMPLATE_ID_DC__":     "Data Center Rolling Upgrade",
        "__TEMPLATE_ID_HOTFIX__": "Emergency Hotfix (No Checks)",
    }
    for hg in data.get("data", []):
        # Strip metadata keys
        hg = {k: v for k, v in hg.items() if not k.startswith("_")}

        wt_ref = hg.get("workflow_template")
        if isinstance(wt_ref, str) and wt_ref in name_map:
            real_name = name_map[wt_ref]
            hg["workflow_template"] = lookup("workflow_template", real_name)

        safe_create(api, "/api/plugins/swim/hardware-groups/", hg, ["slug"], "HardwareGroup", "hardware_group")


def load_12_software_images(api, data):
    """Software Images — resolve platform and file_server IDs"""
    platform_map = {
        "__PLATFORM_ID_IOSXE__": "cisco-ios-xe",
        "__PLATFORM_ID_IOS__":   "cisco-ios",
        "__PLATFORM_ID_NXOS__":  "cisco-nx-os",
        "__PLATFORM_ID_IOSXR__": "cisco-ios-xr",
    }
    fs_map = {
        "__FILESERVER_ID_SJ_HTTP__":  "SJ-HTTP-SRV",
        "__FILESERVER_ID_SJ_TFTP__":  "SJ-TFTP-SRV",
        "__FILESERVER_ID_GLOBAL__":   "Global-HTTPS-Repo",
        "__FILESERVER_ID_NY_SCP__":   "NY-SCP-SRV",
    }
    for img in data.get("data", []):
        # Strip metadata keys
        img = {k: v for k, v in img.items() if not k.startswith("_")}

        # Resolve platform
        p_ref = img.get("platform")
        if isinstance(p_ref, str) and p_ref in platform_map:
            slug = platform_map[p_ref]
            img["platform"] = lookup("platform", slug)

        # Resolve file_server
        fs_ref = img.get("file_server")
        if isinstance(fs_ref, str) and fs_ref in fs_map:
            name = fs_map[fs_ref]
            img["file_server"] = lookup("file_server", name)

        safe_create(api, "/api/plugins/swim/software-images/", img, ["image_name"], "SoftwareImage", "software_image")


def load_13_golden_images(api, data):
    """Golden Images — resolve image and hardware_group IDs"""
    image_map = {
        "__IMAGE_ID_C9300_CAMPUS__": "Cat9k-IOS-XE-17.09.05",
        "__IMAGE_ID_C9200_CAMPUS__": "Cat9200-IOS-XE-17.09.05",
        "__IMAGE_ID_SDWAN__":        "Cat9k-SDWAN-17.09.05",
        "__IMAGE_ID_NXOS__":         "NX-OS-10.3(2)F",
    }
    for gi in data.get("data", []):
        # Strip metadata keys
        gi = {k: v for k, v in gi.items() if not k.startswith("_")}

        img_ref = gi.get("image")
        if isinstance(img_ref, str) and img_ref in image_map:
            real_name = image_map[img_ref]
            gi["image"] = lookup("software_image", real_name)

        if not gi.get("image"):
            fail(f"Cannot resolve image for golden image: {gi}")
            continue

        # Golden images have composite uniqueness (image + deployment_mode)
        existing = find_existing(api, "/api/plugins/swim/golden-images/",
                                 ["image", "deployment_mode"], gi)
        if existing:
            skip(f"GoldenImage for image={gi['image']} mode={gi.get('deployment_mode')} already exists")
            register("golden_image", f"{gi['image']}_{gi.get('deployment_mode')}", existing["id"])
            continue

        r = api.post("/api/plugins/swim/golden-images/", gi)
        if r.status_code in (200, 201):
            obj_id = r.json()["id"]
            ok(f"Created GoldenImage (id={obj_id}) mode={gi.get('deployment_mode')}")
        elif "already exists" in r.text.lower() or "unique" in r.text.lower():
            skip(f"GoldenImage already exists (API constraint)")
        else:
            fail(f"GoldenImage failed: {r.status_code} — {r.text[:300]}")


# ──────────────────────────────────────────────────────────────
# Pre-seed pass: index existing objects in NetBox so 
# cross-references work even if earlier steps are skipped
# ──────────────────────────────────────────────────────────────

def preseed_registry(api):
    """Fetch existing objects to populate the ID registry before loading."""
    info("Pre-seeding registry from existing NetBox objects...")

    index_configs = [
        ("/api/dcim/manufacturers/",             "manufacturer",       "slug"),
        ("/api/dcim/platforms/",                  "platform",           "slug"),
        ("/api/dcim/device-types/",              "device_type",        "slug"),
        ("/api/dcim/regions/",                   "region",             "slug"),
        ("/api/dcim/sites/",                     "site",               "slug"),
        ("/api/dcim/device-roles/",              "device_role",        "slug"),
        ("/api/dcim/devices/",                   "device",             "name"),
        ("/api/plugins/swim/file-servers/",      "file_server",        "name"),
        ("/api/plugins/swim/validation-checks/", "validation_check",   "name"),
        ("/api/plugins/swim/check-templates/",   "check_template",     "name"),
        ("/api/plugins/swim/workflow-templates/", "workflow_template",  "name"),
        ("/api/plugins/swim/hardware-groups/",   "hardware_group",     "slug"),
        ("/api/plugins/swim/software-images/",   "software_image",     "image_name"),
    ]

    for endpoint, obj_type, key_field in index_configs:
        try:
            objects = api.get_list(endpoint)
            for obj in objects:
                natural = obj.get(key_field)
                if natural:
                    register(obj_type, natural, obj["id"])
        except Exception as e:
            info(f"Could not pre-index {endpoint}: {e}")

    info(f"Registry pre-seeded with {len(ID_REGISTRY)} existing objects")


# ──────────────────────────────────────────────────────────────
# Main orchestrator
# ──────────────────────────────────────────────────────────────

STEP_MAP = {
    "01": load_01_manufacturers_platforms,
    "02": load_02_device_types,
    "03": load_03_sites_regions,
    "04": load_04_device_roles,
    "05": load_05_devices,
    "06": load_06_file_servers,
    "07": load_07_validation_checks,
    "08": load_08_check_templates,
    "09": load_09_workflow_templates,
    "10": load_10_workflow_steps,
    "11": load_11_hardware_groups,
    "12": load_12_software_images,
    "13": load_13_golden_images,
}


def main():
    parser = argparse.ArgumentParser(description="SWIM Seed Data Loader")
    parser.add_argument("--url",   default=os.environ.get("NETBOX_URL", "http://localhost:8000"),
                        help="NetBox base URL (default: $NETBOX_URL or http://localhost:8000)")
    parser.add_argument("--token", default=os.environ.get("NETBOX_TOKEN", ""),
                        help="NetBox API token (default: $NETBOX_TOKEN)")
    parser.add_argument("--steps", default=None,
                        help="Comma-separated list of step numbers to run (e.g. '01,02,07'). Default: all.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse files only, do not make API calls.")
    args = parser.parse_args()

    if not args.token:
        sys.exit("Error: Provide --token or set NETBOX_TOKEN environment variable.")

    print(f"\n{'='*60}")
    print(f"  SWIM Seed Data Loader")
    print(f"  Target: {args.url}")
    print(f"{'='*60}\n")

    api = NetBoxAPI(args.url, args.token)
    preseed_registry(api)

    # Determine which steps to run
    script_dir = os.path.dirname(os.path.abspath(__file__))
    requested = args.steps.split(",") if args.steps else sorted(STEP_MAP.keys())

    for step_num in requested:
        step_num = step_num.strip().zfill(2)
        if step_num not in STEP_MAP:
            fail(f"Unknown step: {step_num}")
            continue

        # Find the JSON file
        json_files = [f for f in os.listdir(script_dir)
                      if f.startswith(f"{step_num}_") and f.endswith(".json")]
        if not json_files:
            fail(f"No JSON file found for step {step_num}")
            continue

        json_path = os.path.join(script_dir, sorted(json_files)[0])
        print(f"\n{CYAN}━━━ Step {step_num}: {json_files[0]} ━━━{RESET}")

        with open(json_path, "r") as f:
            data = json.load(f)

        if args.dry_run:
            info(f"[DRY RUN] Parsed {json_files[0]} — {len(data.get('data', data.get('manufacturers', data.get('regions', []))))} entries")
            continue

        loader = STEP_MAP[step_num]
        try:
            loader(api, data)
        except Exception as e:
            fail(f"Step {step_num} encountered an error: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  Seed loading complete. {len(ID_REGISTRY)} objects in registry.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
