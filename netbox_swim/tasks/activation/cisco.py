from unicon.eal.dialogs import Dialog, Statement
from ..base import ScrapliTask, NetmikoTask, UniconTask

class CiscoActivateLogicMixin:
    """Configures the boot variable on a Cisco device to point to the newly distributed software image."""
    
    def _execute_activation(self, device, target_image):
        if not target_image:
            raise ValueError("Target SoftwareImage missing.")
            
        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"
        
        config_commands = [
            f"no boot system",
            f"boot system {dest_path}"
        ]
        
        save_cmd = "write memory"
        
        return self._push_config_and_save(config_commands, save_cmd, dest_path)

    def _push_config_and_save(self, config_commands, save_cmd, dest_path):
        raise NotImplementedError


class CiscoActivateScrapli(ScrapliTask, CiscoActivateLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Scrapli activation is pending future implementation.")


class CiscoActivateNetmiko(NetmikoTask, CiscoActivateLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Netmiko activation is pending future implementation.")


class CiscoActivateUnicon(UniconTask, CiscoActivateLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        if not target_image:
            return [("SKIP", "No target image assigned.")]
            
        # Hard lock: Only Catalyst 9300 INSTALL mode supported for now
        model = getattr(getattr(device, 'device_type', None), 'model', '').upper()
        if '9300' not in model:
            return [("FAIL", f"Activation is currently only supported for Catalyst 9300 series. Found: {model}")]
            
        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"
        
        with self.connect(device, connection_timeout=60) as pyats_device:
            # 1. Check if device is running in INSTALL mode
            try:
                version_out = pyats_device.execute("show version | include Mode")
                if "INSTALL" not in version_out:
                    return [("FAIL", f"Device is NOT in INSTALL mode. BUNDLE mode activation is pending future implementation. Current mode: {version_out.strip()}")]
                    
                # INSTALL mode (Cat9k etc requires install add file ... activate commit)
                cmd = f"install add file {dest_path} activate commit"
                
                dialog = Dialog([
                    Statement(pattern=r'This operation may require a reload of the system.*\[y/n\]', action='sendline(y)', loop_continue=True),
                    Statement(pattern=r'\[y/n\]', action='sendline(y)', loop_continue=True),
                    Statement(pattern=r'Do you want to proceed with reload\?', action='sendline(y)', loop_continue=True)
                ])
                
                try:
                    out = pyats_device.execute(cmd, timeout=3600, reply=dialog)
                    if "Error" in out or "Failed" in out:
                        return [("FAIL", f"INSTALL mode activation failed: {out}")]
                    return [("PASS", f"INSTALL mode activation initiated. Device will reload. Output: {out}")]
                except Exception as e:
                    return [("FAIL", f"INSTALL mode activation exception: {str(e)}")]
            except Exception as e:
                return [("FAIL", f"Failed to verify mode or execute activation: {str(e)}")]
