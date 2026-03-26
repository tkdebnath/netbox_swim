from dcim.models import DeviceType, Platform
from ..base import ScrapliTask, NetmikoTask, UniconTask

from ...parsers.cisco import (
    CiscoShowVersionParser, 
    CiscoShowInventoryParser, 
    CiscoShowTacacsParser
)


class CiscoSyncLogicMixin:
    """
    Vendor-specific diff/save logic for Cisco devices.
    Operates on the standardized schema returned by parsers.
    """

    def _get_or_create_device_type(self, model_str, platform_slug, part_number=None,
                                    manufacturer=None, platform=None):
        """
        Resolves a DeviceType by model string using a 3-level lookup.
        If no match is found, auto-creates the DeviceType.

        Manufacturer resolution priority:
          1. Explicit `manufacturer` kwarg (Manufacturer object, name, or slug string)
          2. `platform.manufacturer` — NetBox Platform FK (most reliable when set)
          3. Inferred from `platform_slug` string (cisco/juniper/arista/panos)

        Returns: (device_type, created: bool)
        """
        import re
        from dcim.models import DeviceType, Manufacturer

        # --- 3-level DeviceType lookup ---
        obj = (
            DeviceType.objects.filter(model=model_str).first()
            or DeviceType.objects.filter(model__iexact=model_str).first()
            or DeviceType.objects.filter(model__icontains=model_str.split('-')[0]).first()
        )
        if obj:
            return obj, False

        # --- Manufacturer resolution (3-tier) ---
        resolved_manufacturer = None

        # Tier 1: explicit argument (Manufacturer object or name/slug string)
        if manufacturer:
            if hasattr(manufacturer, 'pk'):  # Already a Manufacturer model object
                resolved_manufacturer = manufacturer
            else:
                mfr_str = str(manufacturer)
                resolved_manufacturer = (
                    Manufacturer.objects.filter(slug=mfr_str).first()
                    or Manufacturer.objects.filter(name__iexact=mfr_str).first()
                )

        # Tier 2: platform.manufacturer FK (set in NetBox Platform definition)
        if not resolved_manufacturer and platform:
            resolved_manufacturer = getattr(platform, 'manufacturer', None)

        # Tier 3: infer vendor hint from platform_slug string
        if not resolved_manufacturer:
            slug_lower = (platform_slug or '').lower()
            if 'juniper' in slug_lower or 'junos' in slug_lower:
                vendor_hint = 'juniper'
            elif 'arista' in slug_lower or 'eos' in slug_lower:
                vendor_hint = 'arista'
            elif 'palo' in slug_lower or 'panos' in slug_lower:
                vendor_hint = 'palo-alto'
            else:
                vendor_hint = 'cisco'  # default for IOS / IOS-XE / NX-OS

            resolved_manufacturer = (
                Manufacturer.objects.filter(slug=vendor_hint).first()
                or Manufacturer.objects.filter(name__iexact=vendor_hint).first()
            )
            if not resolved_manufacturer:
                mfr_name = vendor_hint.replace('-', ' ').title()
                mfr_slug = re.sub(r'[^a-z0-9-]', '-', vendor_hint.lower()).strip('-')
                resolved_manufacturer, _ = Manufacturer.objects.get_or_create(
                    slug=mfr_slug,
                    defaults={'name': mfr_name}
                )

        # --- Generate unique slug ---
        base_slug = re.sub(r'[^a-z0-9-]', '-', model_str.lower()).strip('-')
        slug = base_slug
        counter = 1
        while DeviceType.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        device_type, created = DeviceType.objects.get_or_create(
            model=model_str,
            defaults={
                'manufacturer': resolved_manufacturer,
                'slug': slug,
                'part_number': part_number or '',
            }
        )
        return device_type, created

    def _get_or_create_platform(self, name, slug=None, manufacturer=None, platform_slug_hint=None):
        """
        Resolves a Platform by name/slug using a 3-level lookup.
        If no match is found, auto-creates the Platform.

        Args:
            name             : Platform name (e.g. 'Cisco IOS-XE')
            slug             : Optional explicit slug. Auto-generated from name if omitted.
            manufacturer     : Optional Manufacturer object or name/slug string to link.
            platform_slug_hint: Optional platform slug string to infer manufacturer if
                               manufacturer arg is not given.

        Returns: (platform, created: bool)
        """
        import re
        from dcim.models import Platform, Manufacturer

        # 3-level lookup
        obj = (
            Platform.objects.filter(slug=slug).first() if slug else None
        ) or (
            Platform.objects.filter(name__iexact=name).first()
        ) or (
            Platform.objects.filter(slug__icontains=name.lower().split()[0]).first()
        )
        if obj:
            return obj, False

        # --- Manufacturer resolution (same 3-tier as _get_or_create_device_type) ---
        resolved_manufacturer = None
        if manufacturer:
            if hasattr(manufacturer, 'pk'):
                resolved_manufacturer = manufacturer
            else:
                mfr_str = str(manufacturer)
                resolved_manufacturer = (
                    Manufacturer.objects.filter(slug=mfr_str).first()
                    or Manufacturer.objects.filter(name__iexact=mfr_str).first()
                )

        if not resolved_manufacturer and platform_slug_hint:
            slug_lower = platform_slug_hint.lower()
            if 'juniper' in slug_lower or 'junos' in slug_lower:
                vendor_hint = 'juniper'
            elif 'arista' in slug_lower or 'eos' in slug_lower:
                vendor_hint = 'arista'
            elif 'palo' in slug_lower or 'panos' in slug_lower:
                vendor_hint = 'palo-alto'
            else:
                vendor_hint = 'cisco'
            resolved_manufacturer = (
                Manufacturer.objects.filter(slug=vendor_hint).first()
                or Manufacturer.objects.filter(name__iexact=vendor_hint).first()
            )

        # Generate slug if not explicitly provided
        auto_slug = slug or re.sub(r'[^a-z0-9-]', '-', name.lower()).strip('-')
        counter = 1
        final_slug = auto_slug
        while Platform.objects.filter(slug=final_slug).exists():
            final_slug = f"{auto_slug}-{counter}"
            counter += 1

        defaults = {'name': name, 'slug': final_slug}
        if resolved_manufacturer:
            defaults['manufacturer'] = resolved_manufacturer

        platform_obj, created = Platform.objects.get_or_create(
            name=name,
            defaults=defaults
        )
        return platform_obj, created

    def _process_cisco_ios_facts(self, device, golden_schema, auto_update, raw_version="", parser_instance=None):
        from ...models import DeviceSyncRecord
        record = DeviceSyncRecord.objects.filter(device=device, status='syncing').last()

        if not golden_schema.get('version'):
            tfsm_plat = getattr(parser_instance, 'textfsm_platform', 'Unknown') if parser_instance else 'Unknown'
            genie_plat = getattr(parser_instance, 'genie_platform', 'Unknown') if parser_instance else 'Unknown'
            msg = (
                f"Both TextFSM and Genie failed to parse 'show version'.\n"
                f"Mapped parsers -> TextFSM: {tfsm_plat} | Genie: {genie_plat}\n"
                f"Raw Device Output:\n{raw_version[:800]}"
            )
            if record:
                record.status = 'failed'
                record.log_messages.append(msg)
                record.save()
            return [("error", msg)]

        changes_made = []
        diff_dictionary = {}
        
        live_hostname = golden_schema.get('hostname')
        live_hardware = golden_schema.get('hardware')
        live_version = golden_schema.get('version')
        live_serial = golden_schema.get('serial')
        live_part_number = golden_schema.get('part_number')
        live_manufacturer = golden_schema.get('manufacturer')  # e.g. 'Cisco' from parser
        live_platform_name = golden_schema.get('platform')     # e.g. 'Cisco IOS-XE 17.x' from parser

        # 1. Check Hostname
        if live_hostname and device.name != live_hostname:
            diff_dictionary['hostname'] = {'old': device.name, 'new': live_hostname}
            device.name = live_hostname
            changes_made.append(f"Updated Hostname to {live_hostname}")

        # 2. Check Device Type (Model)
        if live_hardware:
            current_model = getattr(device.device_type, 'model', '')
            if current_model != live_hardware:
                try:
                    platform_slug = getattr(device.platform, 'slug', '')
                    new_device_type, created = self._get_or_create_device_type(
                        live_hardware, platform_slug,
                        part_number=live_part_number,
                        platform=device.platform,
                        manufacturer=live_manufacturer,  # explicit from parser
                    )
                    diff_dictionary['model'] = {'old': current_model, 'new': new_device_type.model}
                    device.device_type = new_device_type
                    action = 'Auto-Created' if created else 'Updated'
                    changes_made.append(f"{action} Device Type to {new_device_type.model} (from '{live_hardware}')")
                except Exception as e:
                    changes_made.append(f"DeviceType lookup/create failed for '{live_hardware}': {e}")

        # 2b. Check Part Number (via DeviceType.part_number)
        if live_part_number:
            current_part = getattr(device.device_type, 'part_number', '')
            if current_part != live_part_number:
                try:
                    # If model check already resolved/created the device_type, just update part_number on it
                    if diff_dictionary.get('model') and device.device_type:
                        if not device.device_type.part_number:
                            device.device_type.part_number = live_part_number
                            device.device_type.save(update_fields=['part_number'])
                        diff_dictionary['part_number'] = {'old': current_part, 'new': live_part_number}
                        changes_made.append(f"Updated Part Number to {live_part_number} on DeviceType {device.device_type.model}")
                    else:
                        # Independent part_number lookup/create
                        platform_slug = getattr(device.platform, 'slug', '')
                        matched_dt = (
                            DeviceType.objects.filter(part_number=live_part_number).first()
                            or DeviceType.objects.filter(part_number__iexact=live_part_number).first()
                            or DeviceType.objects.filter(part_number__icontains=live_part_number.split('-')[0]).first()
                        )
                        if matched_dt:
                            diff_dictionary['part_number'] = {'old': current_part, 'new': matched_dt.part_number}
                            device.device_type = matched_dt
                            changes_made.append(f"Updated Device Type via Part Number match: {matched_dt.part_number}")
                        else:
                            # No match — auto-create DeviceType keyed by part_number as the model
                            new_dt, created = self._get_or_create_device_type(
                                live_part_number, platform_slug,
                                part_number=live_part_number,
                                platform=device.platform,
                                manufacturer=live_manufacturer,  # explicit from parser
                            )
                            diff_dictionary['part_number'] = {'old': current_part, 'new': new_dt.part_number}
                            device.device_type = new_dt
                            action = 'Auto-Created' if created else 'Linked'
                            changes_made.append(f"{action} DeviceType for Part Number '{live_part_number}'")
                except Exception as e:
                    changes_made.append(f"Part number lookup/create failed for '{live_part_number}': {e}")

        # 2c. Check/create Platform (name reported by device vs. NetBox)
        #     Must run BEFORE 2d so manufacturer back-fill targets the correct platform object.
        if live_platform_name:
            current_platform_name = getattr(device.platform, 'name', None)
            if current_platform_name != live_platform_name:
                try:
                    platform_slug = getattr(device.platform, 'slug', '')
                    # Use the Manufacturer object already resolved from DeviceType (same record).
                    # Fall back to the raw parser string only if DeviceType has no manufacturer.
                    resolved_mfr = (
                        getattr(device.device_type, 'manufacturer', None)
                        or live_manufacturer
                    )
                    new_platform, created = self._get_or_create_platform(
                        name=live_platform_name,
                        manufacturer=resolved_mfr,
                        platform_slug_hint=platform_slug,
                    )
                    diff_dictionary['platform'] = {'old': current_platform_name, 'new': new_platform.name}
                    device.platform = new_platform
                    action = 'Auto-Created' if created else 'Updated'
                    changes_made.append(f"{action} Platform to '{new_platform.name}'")
                except Exception as e:
                    changes_made.append(f"Platform lookup/create failed for '{live_platform_name}': {e}")

        # 2d. Back-fill Platform.manufacturer from the resolved DeviceType.manufacturer
        #     Runs after 2c so device.platform is the final, correct platform object.
        if device.platform and device.device_type:
            resolved_mfr = getattr(device.device_type, 'manufacturer', None)
            platform_mfr = getattr(device.platform, 'manufacturer', None)
            if resolved_mfr and not platform_mfr:
                try:
                    device.platform.manufacturer = resolved_mfr
                    device.platform.save(update_fields=['manufacturer'])
                    diff_dictionary['platform_manufacturer'] = {
                        'old': None,
                        'new': resolved_mfr.name
                    }
                    changes_made.append(
                        f"Back-filled Platform '{device.platform.name}' manufacturer "
                        f"to '{resolved_mfr.name}' (sourced from DeviceType)"
                    )
                except Exception as e:
                    changes_made.append(f"Platform manufacturer update failed: {e}")

        # 3. Check Serial
        if live_serial and device.serial != live_serial:
            diff_dictionary['serial'] = {'old': device.serial, 'new': live_serial}
            device.serial = live_serial
            changes_made.append(f"Updated Serial to {live_serial}")
        
        # 4. Check SWIM OS Version
        if live_version:
            current_cf_version = device.custom_field_data.get('software_version')
            if current_cf_version != live_version:
                diff_dictionary['software_version'] = {'old': current_cf_version, 'new': live_version}
                device.custom_field_data['software_version'] = live_version
                changes_made.append(f"Updated OS Version to {live_version}")
                
        # 5. Check TACACS & VRF Custom Fields
        for cf_key in ['tacacs_source_interface', 'tacacs_source_ip', 'vrf']:
            live_val = golden_schema.get(cf_key)
            if live_val is not None:
                current_val = device.custom_field_data.get(cf_key)
                if current_val != live_val:
                    diff_dictionary[cf_key] = {'old': current_val, 'new': live_val}
                    device.custom_field_data[cf_key] = live_val
                    changes_made.append(f"Updated {cf_key} to {live_val}")

        from ...models import DeviceSyncRecord

        # Check if we have an active record from the engine to update
        record = DeviceSyncRecord.objects.filter(device=device, status='syncing').last()

        # Save logic based on auto_update flag
        if changes_made:
            if auto_update:
                if not record:
                    record = DeviceSyncRecord.objects.create(device=device)
                record.status = 'auto_applied'
                record.detected_diff = diff_dictionary
                record.live_facts = golden_schema
                record.log_messages = changes_made
                record.save()
                return [("pass", f"Auto-Applied: {', '.join(changes_made)}")]
            else:
                if not record:
                    record = DeviceSyncRecord.objects.create(device=device)
                record.status = 'pending'
                record.detected_diff = diff_dictionary
                record.live_facts = golden_schema
                record.log_messages = [f"Found {len(changes_made)} differences."] + changes_made
                record.save()
                return [("info", f"Differences detected. Placed in Pending state: {', '.join(changes_made)}")]
        
        # Perfect Match Audit Trail # user request: "incase there is no change found then status should ne no change"
        if not record:
            record = DeviceSyncRecord.objects.create(device=device)
        record.status = 'no_change'
        record.detected_diff = {}
        record.live_facts = golden_schema
        record.log_messages = ["Validation complete: Device aligns with NetBox data."]
        record.save()
        return [("info", "Device in sync. No updates needed.")]


class SyncCiscoIosDeviceScrapli(ScrapliTask, CiscoSyncLogicMixin):
    """Sync an IOS-XE device globally through Scrapli."""

    def execute(self, device, target_image=None, auto_update=False):
        host = str(device.primary_ip.address.ip) if device.primary_ip else 'unknown'
        try:
            with self.connect(device) as conn:
                slug = getattr(device.platform, 'slug', 'cisco_ios')

                hostname = None
                response_prompt = conn.get_prompt()
                if response_prompt:
                    hostname = response_prompt.replace("#", "").replace(">", "").strip()

                response_ver = conn.send_command("show version")
                parser_ver = CiscoShowVersionParser(raw_string=response_ver.result, platform_slug=slug)
                golden_schema = parser_ver.get_facts()

                if hostname:
                    golden_schema['hostname'] = hostname

                response_inv = conn.send_command("show inventory")
                parser_inv = CiscoShowInventoryParser(raw_string=response_inv.result, platform_slug=slug)
                for k, v in parser_inv.get_facts().items():
                    if v: golden_schema[k] = v

                response_run = conn.send_command("show running-config")
                response_interface = conn.send_command("show interface")

                fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
                tacacs_dict = {
                    'run': response_run.result,
                    'interface': response_interface.result,
                    'fallback_ip': fallback_ip
                }

                parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
                for k, v in parser_tacacs.get_facts().items():
                    if v: golden_schema[k] = v

                return self._process_cisco_ios_facts(
                    device, golden_schema, auto_update,
                    response_ver.result if hasattr(response_ver, 'result') else str(response_ver),
                    parser_ver
                )
        except Exception as e:
            msg = (
                f"[Scrapli] Connection to {device.name} ({host}:22) FAILED: "
                f"{type(e).__name__}: {e}"
            )
            return [("error", msg)]


class SyncCiscoIosDeviceNetmiko(NetmikoTask, CiscoSyncLogicMixin):
    """Sync logic explicitly for Netmiko."""

    def execute(self, device, target_image=None, auto_update=False):
        host = str(device.primary_ip.address.ip) if device.primary_ip else 'unknown'
        try:
            with self.connect(device) as conn:
                slug = device.platform.slug if device.platform else 'cisco_ios'

                hostname = None
                response_prompt = conn.get_prompt()
                if response_prompt:
                    hostname = response_prompt.replace("#", "").replace(">", "").strip()

                response_ver = conn.send_command("show version")
                parser_ver = CiscoShowVersionParser(raw_string=response_ver, platform_slug=slug)
                golden_schema = parser_ver.get_facts()

                if hostname:
                    golden_schema['hostname'] = hostname

                response_inv = conn.send_command("show inventory")
                parser_inv = CiscoShowInventoryParser(raw_string=response_inv, platform_slug=slug)
                for k, v in parser_inv.get_facts().items():
                    if v: golden_schema[k] = v

                response_run = conn.send_command("show running-config")
                response_interface = conn.send_command("show interface")

                fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
                tacacs_dict = {
                    'run': response_run,
                    'interface': response_interface,
                    'fallback_ip': fallback_ip
                }

                parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
                for k, v in parser_tacacs.get_facts().items():
                    if v: golden_schema[k] = v

                return self._process_cisco_ios_facts(
                    device, golden_schema, auto_update, str(response_ver), parser_ver
                )
        except Exception as e:
            msg = (
                f"[Netmiko] Connection to {device.name} ({host}:22) FAILED: "
                f"{type(e).__name__}: {e}"
            )
            return [("error", msg)]


class SyncCiscoIosDeviceUnicon(UniconTask, CiscoSyncLogicMixin):
    """Sync logic explicitly for Unicon."""

    def execute(self, device, target_image=None, auto_update=False):
        host = str(device.primary_ip.address.ip) if device.primary_ip else 'unknown'
        try:
            with self.connect(device, log_stdout=True, learn_hostname=True) as conn:
                slug = device.platform.slug if device.platform else 'cisco_ios'

                hostname = None
                if hasattr(device, 'learned_hostname') and device.learned_hostname:
                    hostname = device.learned_hostname

                response_ver = conn.execute("show version")
                parser_ver = CiscoShowVersionParser(raw_string=response_ver, platform_slug=slug)
                golden_schema = parser_ver.get_facts()

                if hostname:
                    golden_schema['hostname'] = hostname

                response_inv = conn.execute("show inventory")
                parser_inv = CiscoShowInventoryParser(raw_string=response_inv, platform_slug=slug)
                for k, v in parser_inv.get_facts().items():
                    if v: golden_schema[k] = v

                response_run = conn.execute("show running-config")
                response_interface = conn.execute("show interface")

                fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
                tacacs_dict = {
                    'run': response_run,
                    'interface': response_interface,
                    'fallback_ip': fallback_ip
                }

                parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
                for k, v in parser_tacacs.get_facts().items():
                    if v: golden_schema[k] = v

                return self._process_cisco_ios_facts(
                    device, golden_schema, auto_update, str(response_ver), parser_ver
                )
        except Exception as e:
            msg = (
                f"[Unicon] Connection to {device.name} ({host}:22) FAILED: "
                f"{type(e).__name__}: {e}"
            )
            return [("error", msg)]