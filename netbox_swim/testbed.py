"""
pyATS / Genie Testbed Generator

Dynamically generates pyATS testbed YAML from NetBox device inventory.
This enables engineers to:
  - Download a ready-to-use testbed.yaml for Genie learn/diff
  - Use the testbed with `genie learn` and `genie diff` CLI commands
  - Run pre/post checks outside of the SWIM engine workflow

Follows the pyATS testbed best-practice from:
  https://developer.cisco.com/codeexchange/github/repo/hpreston/intro-network-tests/

Credentials are referenced via %ENV{VAR} syntax so no secrets are
ever written to the YAML file.  The variable names match the exact
same environment variables the SWIM engine reads at runtime
(defined in env/swim.env):

  Default:       SWIM_USERNAME,           SWIM_PASSWORD,           SWIM_SECRET
  Lab:           LAB_CREDS_USERNAME,      LAB_CREDS_PASSWORD,      LAB_CREDS_SECRET
  Site B:        SITE_B_CREDS_USERNAME,   SITE_B_CREDS_PASSWORD,   SITE_B_CREDS_SECRET
  Core HQ:       CORE_HQ_CREDS_USERNAME,  CORE_HQ_CREDS_PASSWORD,  CORE_HQ_CREDS_SECRET

  Per-device overrides come from NetBox config context:
    swim.credential_profile = 'LAB_CREDS' | 'SITE_B_CREDS' | 'CORE_HQ_CREDS' | ...
"""

import yaml
import logging

logger = logging.getLogger('netbox_swim')


# ================================================================
# Public API
# ================================================================

def generate_testbed_yaml(devices, credential_profile=None, include_topology=False):
    """
    Generate a pyATS testbed dict from a queryset of NetBox Device objects.

    Args:
        devices:            QuerySet or list of NetBox Device objects
        credential_profile: Optional global override for the credential env-var
                            prefix (e.g. 'LAB_CREDS' → LAB_CREDS_USERNAME)
        include_topology:   Reserved for future topology-link metadata

    Returns:
        dict – ready to be dumped to YAML with `testbed_dict_to_yaml()`
    """
    from .constants import PLATFORM_MAPPINGS

    # ---- Determine the default credential variable prefix ----
    # If caller provides one, use it; otherwise SWIM is the default.
    default_prefix = (credential_profile or 'SWIM').upper()

    # ---- Testbed-level shared credentials ----
    # Following the hpreston/intro-network-tests pattern:
    #   default – SSH login (username + password)
    #   enable  – enable/privilege-exec secret
    #   line    – line/console password (typically same as default password)
    testbed_creds = {
        'default': {
            'username': f'%ENV{{{default_prefix}_USERNAME}}',
            'password': f'%ENV{{{default_prefix}_PASSWORD}}',
        },
        'enable': {
            'password': f'%ENV{{{default_prefix}_SECRET}}',
        },
        'line': {
            'password': f'%ENV{{{default_prefix}_PASSWORD}}',
        },
    }

    testbed_dict = {
        'testbed': {
            'name': 'SWIM_NetBox_Testbed',
            'credentials': testbed_creds,
        },
        'devices': {},
    }

    for device in devices:
        # Skip devices without a primary IP — can't connect
        if not device.primary_ip:
            logger.warning(f"Skipping {device.name}: No primary IP assigned")
            continue

        ip = str(device.primary_ip.address.ip)
        platform_slug = (
            getattr(device.platform, 'slug', 'cisco-ios-xe')
            if device.platform else 'cisco-ios-xe'
        )
        dialect = PLATFORM_MAPPINGS.get(platform_slug, PLATFORM_MAPPINGS['default'])

        # Sanitised hostname for the YAML key
        dev_name = str(device.name or f"device_{device.pk}")

        # ---- Read device config context for credential profile ----
        config_context = {}
        try:
            config_context = device.get_config_context()
        except Exception:
            pass

        swim_config = config_context.get('swim', {})
        device_profile = swim_config.get('credential_profile', '').upper()

        device_entry = {
            'os': dialect['genie'],
            'type': _get_device_type_label(device),
            'connections': {
                'cli': {
                    'protocol': 'ssh',
                    'ip': ip,
                    'ssh_options': _build_ssh_options(),
                },
            },
            'custom': {
                'netbox_id': device.pk,
                'site': str(device.site) if device.site else None,
                'role': str(device.role) if device.role else None,
                'platform_slug': platform_slug,
                'model': str(device.device_type) if device.device_type else None,
            },
        }

        # Only inject per-device credentials when the device uses a
        # DIFFERENT profile from the testbed-level default.
        # This keeps the YAML DRY — most devices inherit testbed creds.
        #
        # Real examples from swim.env:
        #   credential_profile = 'LAB_CREDS'      → LAB_CREDS_USERNAME / _PASSWORD / _SECRET
        #   credential_profile = 'SITE_B_CREDS'   → SITE_B_CREDS_USERNAME / ...
        #   credential_profile = 'CORE_HQ_CREDS'  → CORE_HQ_CREDS_USERNAME / ...
        if device_profile and device_profile != default_prefix:
            device_entry['credentials'] = {
                'default': {
                    'username': f'%ENV{{{device_profile}_USERNAME}}',
                    'password': f'%ENV{{{device_profile}_PASSWORD}}',
                },
                'enable': {
                    'password': f'%ENV{{{device_profile}_SECRET}}',
                },
            }

        # Attach TACACS source interface if discovered during sync
        tacacs_intf = device.custom_field_data.get('tacacs_source_interface')
        if tacacs_intf:
            device_entry['custom']['tacacs_source_interface'] = tacacs_intf

        testbed_dict['devices'][dev_name] = device_entry

    return testbed_dict


def testbed_dict_to_yaml(testbed_dict):
    """Serialise the testbed dict into a clean, commented YAML string."""

    class _StrDumper(yaml.SafeDumper):
        pass

    def _str_representer(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    _StrDumper.add_representer(str, _str_representer)

    # Collect every %ENV{} variable referenced anywhere in the testbed
    env_vars = _collect_env_vars(testbed_dict)

    header = (
        "# ============================================================\n"
        "# pyATS Testbed — Auto-Generated from NetBox SWIM Plugin\n"
        "# ============================================================\n"
        "#\n"
        "# Usage:\n"
        "#   genie learn ospf interface routing --testbed-file testbed.yaml\n"
        "#   genie diff pre_snapshot post_snapshot\n"
        "#   genie parse 'show version' --testbed-file testbed.yaml --devices <name>\n"
        "#   pyats run job network_test_job.py --testbed testbed.yaml\n"
        "#\n"
        "# Required environment variables  (source your swim.env):\n"
        "#\n"
    )

    for var in sorted(env_vars):
        header += f"#   export {var}=<value>\n"

    header += (
        "#\n"
        "# Devices inherit testbed-level credentials unless their NetBox\n"
        "# config context sets  swim.credential_profile  to a different\n"
        "# profile name (e.g. LAB_CREDS, SITE_B_CREDS, CORE_HQ_CREDS).\n"
        "#\n"
        "# ============================================================\n\n"
    )

    return header + yaml.dump(
        testbed_dict,
        Dumper=_StrDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


# ================================================================
# Private Helpers
# ================================================================

def _build_ssh_options():
    """Construct SSH client options for legacy device compatibility."""
    return (
        '-o StrictHostKeyChecking=no '
        '-o UserKnownHostsFile=/dev/null '
        '-o KexAlgorithms=+diffie-hellman-group-exchange-sha1,'
        'diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 '
        '-o HostKeyAlgorithms=+ssh-rsa '
        '-o Ciphers=+aes256-cbc'
    )


def _get_device_type_label(device):
    """Return a human-readable type label for the device."""
    if device.device_type:
        manufacturer = getattr(device.device_type.manufacturer, 'name', 'Unknown')
        model = device.device_type.model or 'Unknown'
        return f"{manufacturer} {model}"
    return "router"


def _collect_env_vars(testbed_dict):
    """
    Walk the testbed dict and extract every %ENV{VAR_NAME} reference
    so the YAML header can list all required exports.
    """
    import re
    pattern = re.compile(r'%ENV\{([^}]+)\}')
    found = set()

    def _walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)
        elif isinstance(obj, str):
            for match in pattern.findall(obj):
                found.add(match)

    _walk(testbed_dict)
    return found
