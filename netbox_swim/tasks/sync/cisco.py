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

        # 1. Check Hostname
        if live_hostname and device.name != live_hostname:
            diff_dictionary['hostname'] = {'old': device.name, 'new': live_hostname}
            device.name = live_hostname
            changes_made.append(f"Updated Hostname to {live_hostname}")

        # 2. Check Device Type (Model)
        if live_hardware:
            current_model = getattr(device.device_type, 'model', '')
            if current_model != live_hardware:
                diff_dictionary['model'] = {'old': current_model, 'new': live_hardware}
                try:
                    new_device_type = DeviceType.objects.get(model=live_hardware)
                    device.device_type = new_device_type
                    changes_made.append(f"Updated Device Type to {live_hardware}")
                except DeviceType.DoesNotExist:
                    changes_made.append(f"Discovered model {live_hardware} but it does not exist in NetBox DB.")

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
        with self.connect(device) as conn:
            slug = getattr(device.platform, 'slug', 'cisco_ios')
            
            # Finding actual hostname from prompt
            hostname = None
            response_prompt = conn.get_prompt()
            if response_prompt:
                hostname = response_prompt.replace("#", "").replace(">", "").strip()
            
            # --- 1. Base show version Execution ---
            response_ver = conn.send_command("show version")
            parser_ver = CiscoShowVersionParser(raw_string=response_ver.result, platform_slug=slug)
            golden_schema = parser_ver.get_facts()
            
            # Override Hostname from Prompt execution (Highest Priority!)
            if hostname:
                golden_schema['hostname'] = hostname
            
            # --- 2. Show Inventory Execution ---
            response_inv = conn.send_command("show inventory")
            parser_inv = CiscoShowInventoryParser(raw_string=response_inv.result, platform_slug=slug)
            for k, v in parser_inv.get_facts().items():
                if v: golden_schema[k] = v
            
            # --- 3. TACACS Execution ---
            response_run = conn.send_command("show running-config")
            response_interface = conn.send_command("show interface")
            
            # Extract IP from NetBox object
            fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
            tacacs_dict = {
                'run': response_run.result,
                'interface': response_interface.result,
                'fallback_ip': fallback_ip
            }
            
            parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
            for k, v in parser_tacacs.get_facts().items():
                if v: golden_schema[k] = v
            
            # 4. Hand-off combined schema execution to the checking system
            return self._process_cisco_ios_facts(device, golden_schema, auto_update, response_ver.result if hasattr(response_ver, 'result') else str(response_ver), parser_ver)



class SyncCiscoIosDeviceNetmiko(NetmikoTask, CiscoSyncLogicMixin):
    """Sync logic explicitly for Netmiko."""
    
    def execute(self, device, target_image=None, auto_update=False):
        with self.connect(device) as conn:
            slug = device.platform.slug if device.platform else 'cisco_ios'
            
            # Finding actual hostname from prompt
            hostname = None
            response_prompt = conn.get_prompt()
            if response_prompt:
                hostname = response_prompt.replace("#", "").replace(">", "").strip()
            
            # --- 1. Base show version Execution ---
            response_ver = conn.send_command("show version")
            parser_ver = CiscoShowVersionParser(raw_string=response_ver, platform_slug=slug)
            golden_schema = parser_ver.get_facts()
            
            # Override Hostname from Prompt execution (Highest Priority!)
            if hostname:
                golden_schema['hostname'] = hostname
            
            # --- 2. Show Inventory Execution ---
            response_inv = conn.send_command("show inventory")
            parser_inv = CiscoShowInventoryParser(raw_string=response_inv, platform_slug=slug)
            for k, v in parser_inv.get_facts().items():
                if v: golden_schema[k] = v
            
            # --- 3. TACACS Execution ---
            response_run = conn.send_command("show running-config")
            response_interface = conn.send_command("show interface")
            
            # Extract IP from NetBox object
            fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
            tacacs_dict = {
                'run': response_run,
                'interface': response_interface,
                'fallback_ip': fallback_ip
            }
            
            parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
            for k, v in parser_tacacs.get_facts().items():
                if v: golden_schema[k] = v
            
            # 4. Hand-off combined schema execution to the checking system
            return self._process_cisco_ios_facts(device, golden_schema, auto_update, str(response_ver), parser_ver)


class SyncCiscoIosDeviceUnicon(UniconTask, CiscoSyncLogicMixin):
    """Sync logic explicitly for Unicon."""
    
    def execute(self, device, target_image=None, auto_update=False):
        with self.connect(device, log_stdout=True, learn_hostname=True) as conn:
            slug = device.platform.slug if device.platform else 'cisco_ios'
            
            # Finding actual hostname from prompt
            hostname = None
            if device.learned_hostname:
                hostname = device.learned_hostname
            
            # --- 1. Base show version Execution ---
            response_ver = conn.execute("show version")
            parser_ver = CiscoShowVersionParser(raw_string=response_ver, platform_slug=slug)
            golden_schema = parser_ver.get_facts()
            
            # Override Hostname from Prompt execution (Highest Priority!)
            if hostname:
                golden_schema['hostname'] = hostname
            
            # --- 2. Show Inventory Execution ---
            response_inv = conn.execute("show inventory")
            parser_inv = CiscoShowInventoryParser(raw_string=response_inv, platform_slug=slug)
            for k, v in parser_inv.get_facts().items():
                if v: golden_schema[k] = v
            
            # --- 3. TACACS Execution ---
            response_run = conn.execute("show running-config")
            response_interface = conn.execute("show interface")
            
            # Extract IP from NetBox object
            fallback_ip = str(device.primary_ip).split('/')[0] if device.primary_ip else ''
            tacacs_dict = {
                'run': response_run,
                'interface': response_interface,
                'fallback_ip': fallback_ip
            }
            
            parser_tacacs = CiscoShowTacacsParser(raw_string=tacacs_dict, platform_slug=slug)
            for k, v in parser_tacacs.get_facts().items():
                if v: golden_schema[k] = v
            
            # 4. Hand-off combined schema execution to the checking system
            return self._process_cisco_ios_facts(device, golden_schema, auto_update, str(response_ver), parser_ver)
            