from .base import BaseCommandParser

class CiscoShowVersionParser(BaseCommandParser):
    """
    Parses 'show version' for Cisco IOS/IOS-XE/NX-OS platforms.
    Tries both TextFSM and Genie, merging results for better coverage.
    """
    
    def _initialize_schema(self):
        # Schema expected by CiscoSyncLogicMixin
        return {
            'hostname': None,
            'hardware': None,
            'version': None,
            'serial': None
        }

    def get_facts(self):
        command_used = "show version"
        
        # TextFSM returns a list; show version only has one entry
        textfsm_raw_list = self._parse_with_textfsm(command_used)
        textfsm_data = textfsm_raw_list[0] if (isinstance(textfsm_raw_list, list) and len(textfsm_raw_list) > 0) else {}
        
        genie_data = self._parse_with_genie(command_used)

        # 1. TextFSM Extraction
        if textfsm_data:    
            # Merge any extra extracted fields into our schema
            if isinstance(textfsm_data, dict):
                for k, v in textfsm_data.items():
                    if v and k not in self.structured_facts:
                        self.structured_facts[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
                        
            # IOS vs NXOS keys are different in TextFSM
            if self.textfsm_platform == 'cisco_nxos':
                if not self.structured_facts['hostname']:
                    self.structured_facts['hostname'] = textfsm_data.get('hostname')
                if not self.structured_facts['version']:
                    self.structured_facts['version'] = textfsm_data.get('os')
                if not self.structured_facts['hardware']:
                    self.structured_facts['hardware'] = textfsm_data.get('platform')
                if not self.structured_facts['serial']:
                    serial = textfsm_data.get('serial')
                    self.structured_facts['serial'] = serial[0] if isinstance(serial, list) else serial

            if self.textfsm_platform in ['cisco_ios', 'cisco_iosxe']:
                if not self.structured_facts['hardware']:
                    hw = textfsm_data.get('hardware')
                    self.structured_facts['hardware'] = hw[0] if isinstance(hw, list) and len(hw) > 0 else (hw if not isinstance(hw, list) else None)
                if not self.structured_facts['serial']:
                    serial = textfsm_data.get('serial', [])
                    self.structured_facts['serial'] = serial[0] if isinstance(serial, list) and len(serial) > 0 else (serial if not isinstance(serial, list) else None)
        # 2. Genie fallback for fields TextFSM missed
        if genie_data:
            # IOS vs NXOS keys are different in Genie
            if self.genie_platform == 'nxos':
                if not self.structured_facts['hostname']:
                    self.structured_facts['hostname'] = genie_data.get("platform", {}).get("hardware", {}).get("device_name")
            
                if not self.structured_facts['version']:
                    self.structured_facts['version'] = genie_data.get("platform", {}).get("software", {}).get("system_version")
            
                if not self.structured_facts['hardware']:
                    self.structured_facts['hardware'] = genie_data.get("platform", {}).get("hardware", {}).get("chassis")

                if not self.structured_facts['serial']:
                    self.structured_facts['serial'] = genie_data.get("platform", {}).get("hardware", {}).get("chassis_sn")

            if self.genie_platform in ['ios', 'iosxe']:
                if not self.structured_facts['hostname']:
                    self.structured_facts['hostname'] = genie_data.get("version", {}).get("hostname")
            
                if not self.structured_facts['version']:
                    version = genie_data.get("version", {}).get("version")
                    if not version:
                        version = genie_data.get("version", {}).get("xe_version")
                    self.structured_facts['version'] = version
            
                if not self.structured_facts['hardware']:
                    self.structured_facts['hardware'] = genie_data.get("version", {}).get("chassis")

                if not self.structured_facts['serial']:
                    self.structured_facts['serial'] = genie_data.get("version", {}).get("chassis_sn")

        return self.structured_facts


class CiscoShowInventoryParser(BaseCommandParser):
    """Parses 'show inventory' for hardware model and serial number."""
    def _initialize_schema(self):
        return {
            'hardware': None,
            'serial': None
        }
    
    def get_facts(self):
        command_used = "show inventory"

        # TextFSM returns a list; grab first entry
        textfsm_data = self._parse_with_textfsm(command_used)
        
        # 2. Genie {Not implemented at the moment}
        # genie_data = self._parse_with_genie(command_used)

        # 1. TextFSM Extraction
        if textfsm_data:    
            # Store all inventory items for visibility
            for i, item in enumerate(textfsm_data):
                if isinstance(item, dict):
                    name = item.get('name', f"item_{i}").strip().strip('"')
                    pid = item.get('pid')
                    sn = item.get('sn')
                    if pid: self.structured_facts[f"{name}_pid"] = pid
                    if sn: self.structured_facts[f"{name}_serial"] = sn

            # IOS vs NXOS keys are different in TextFSM
            if self.textfsm_platform == 'cisco_nxos':
                for item in textfsm_data:
                    if item.get('name') == "Chassis":
                        self.structured_facts['hardware'] = item.get('pid')
                        self.structured_facts['serial'] = item.get('sn')
                        break

            elif self.textfsm_platform in ['cisco_ios', 'cisco_iosxe']:
                for item in textfsm_data:
                    # 'name' could be 'Chassis' or '"Chassis"' or empty
                    name = str(item.get('name', '')).strip().strip('"').lower()
                    if name == "chassis" or "chassis" in name:
                        if not self.structured_facts['hardware']:
                            self.structured_facts['hardware'] = item.get('pid')
                        if not self.structured_facts['serial']:
                            self.structured_facts['serial'] = item.get('sn')
                        break
                
                # If "Chassis" was not found (e.g., switches might just list "1" or "Stack"), grab the first item's PID/SN
                if not self.structured_facts['hardware'] and len(textfsm_data) > 0:
                    self.structured_facts['hardware'] = textfsm_data[0].get('pid')
                if not self.structured_facts['serial'] and len(textfsm_data) > 0:
                    self.structured_facts['serial'] = textfsm_data[0].get('sn')

        return self.structured_facts


class CiscoShowTacacsParser(BaseCommandParser):
    """
    Parser for determining the routing path and VRF of the TACACS source.
    Expects self.raw_string to be instantiated as a dictionary:
    {
        'run': '<raw show running-config>',
        'interface': '<raw show interface>',
        'fallback_ip': '10.0.0.1'     # The IP Scrapli actually used to connect
    }
    """
    def _initialize_schema(self):
        return {
            'tacacs_source_interface': None,
            'tacacs_source_ip': None, # Resolved from running-config
            'vrf': None               # Defaults to 'global' if not found in a named VRF
        }
    
    def get_facts(self):
        # 1. Gather inputs configured in your Multi-Stage parser
        run_output = self.raw_string.get('run', '')
        interface_output = self.raw_string.get('interface', '')
        fallback_ip = self.raw_string.get('fallback_ip', '')

        # 2. Pull your standalone helper function
        from .helpers import get_ios_management_context
        
        # 3. Process the huge config block cleanly.
        context = get_ios_management_context(run_output, interface_output, fallback_ip)
        
        if context:
            self.structured_facts['tacacs_source_interface'] = context.get('interface')
            self.structured_facts['tacacs_source_ip'] = context.get('ip_address')
            self.structured_facts['vrf'] = context.get('vrf')

        return self.structured_facts

import re
class CiscoDirFlashParser(BaseCommandParser):
    """
    Parses 'dir flash:' into total and free bytes using Regex.
    """
    def _initialize_schema(self):
        return {
            'total_bytes': 0,
            'free_bytes': 0,
            'total_mb': 0.0,
            'free_mb': 0.0
        }

    def get_facts(self):
        # Regex first – faster than spinning up Genie and handles most IOS/IOS-XE output
        match_storage = re.search(r'([\d,]+)\s+bytes total\s+\(([\d,]+)\s+bytes free\)', self.raw_string, re.IGNORECASE)
        
        if match_storage:
            self.structured_facts['total_bytes'] = int(match_storage.group(1).replace(",", ""))
            self.structured_facts['free_bytes'] = int(match_storage.group(2).replace(",", ""))
        
        else:
            # Fallback to pure genie if Regex fails (e.g. extremely weird terminal lines or NX-OS nuances)
            genie_data = self._parse_with_genie("dir flash:")
            if genie_data and 'dir' in genie_data:
                try:
                    self.structured_facts['total_bytes'] = int(genie_data['dir']['flash:']['bytes_total'])
                    self.structured_facts['free_bytes'] = int(genie_data['dir']['flash:']['bytes_free'])
                except KeyError:
                    pass
                    
        # Calculate derived metrics
        self.structured_facts['total_mb'] = self.structured_facts['total_bytes'] / 1024 / 1024
        self.structured_facts['free_mb'] = self.structured_facts['free_bytes'] / 1024 / 1024
        
        return self.structured_facts


class CiscoRomvarParser(BaseCommandParser):
    """
    Parses 'show romvar' to evaluate config boot overrides.
    """
    def _initialize_schema(self):
        return {
            'is_startup_ignored': False
        }

    def get_facts(self):
        # Check for the explicit boot override flag
        if "SWITCH_IGNORE_STARTUP_CFG=1" in self.raw_string:
            self.structured_facts['is_startup_ignored'] = True
            
        return self.structured_facts
