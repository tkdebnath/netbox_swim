import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask

logger = logging.getLogger('netbox_swim')

class CiscoVerifyScrapli(ScrapliTask):
    def execute(self, device, target_image=None, **kwargs):
        return None, "Scrapli verification not yet implemented. Set connection_priority to 'unicon'."

class CiscoVerifyNetmiko(NetmikoTask):
    def execute(self, device, target_image=None, **kwargs):
        return None, "Netmiko verification not yet implemented. Set connection_priority to 'unicon'."

class CiscoVerifyUnicon(UniconTask):
    """
    Post-Activation Version Verification.
    Connects to the device, retrieves the current running firmware version,
    and compares it to the Job's target_image.version.
    Returns: Tuple(bool success, str output_message)
    """
    
    # Define which device platforms support verification using Unicon/Genie
    SUPPORTED_PLATFORMS = ['ios', 'iosxe', 'nxos']

    def execute(self, device, target_image=None, **kwargs):
        if not target_image or not target_image.version:
            return True, "No target image version defined. Skipping verification."

        os_type = device.platform if hasattr(device, 'platform') and device.platform else 'iosxe'
        if os_type not in self.SUPPORTED_PLATFORMS:
            return False, f"Verification not supported for platform '{os_type}'. Supported: {', '.join(self.SUPPORTED_PLATFORMS)}"

        target_version = str(target_image.version).strip().lower()
        report_output = f"Starting Post-Activation Verification...\nTarget Version: {target_version}\n"

        try:
            with self.connect(device, connection_timeout=60) as pyats_device:
                report_output += f"Connected to {device.name}. Retrieving version...\n"
                
                # Genie automatically handles show version parsing for supported platforms
                parsed_output = pyats_device.parse('show version')
                
                current_version = None
                if isinstance(parsed_output, dict):
                    ver_block = parsed_output.get('version', {})
                    if isinstance(ver_block, dict):
                        current_version = ver_block.get('version') or ver_block.get('version_short')
                    elif isinstance(ver_block, str):
                        current_version = ver_block

                if not current_version:
                    report_output += "Failed to parse version from device output.\n"
                    return False, report_output

                current_version = str(current_version).strip().lower()

                if current_version == target_version:
                    report_output += f"Device Running Version: {current_version}\n"
                    report_output += f"VERIFICATION PASSED: Version matches target ({target_version}).\n"
                    return True, report_output
                else:
                    report_output += f"Device Running Version: {current_version}\n"
                    report_output += f"VERIFICATION FAILED: Expected {target_version}, found {current_version}.\n"
                    return False, report_output

        except Exception as e:
            error_msg = f"Verification error: {str(e)}"
            logger.error(f"[Verification] {device.name}: {error_msg}")
            report_output += f"\n[ERROR] {error_msg}\n"
            return False, report_output
