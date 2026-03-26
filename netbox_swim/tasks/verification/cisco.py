import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask

logger = logging.getLogger('netbox_swim')

class CiscoVerifyLogicMixin:
    def _evaluate_verification(self, device, target_image, version_output):
        if not target_image or not target_image.version:
            return True, "No target image version defined. Skipping verification."
            
        target_version = str(target_image.version).strip().lower()
        report_output = f"Starting Post-Activation Verification...\nTarget Version: {target_version}\n"
        report_output += f"Connected to {device.name}. Retrieving and parsing version...\n"
        
        slug = getattr(device.platform, 'slug', 'cisco_ios')
        from netbox_swim.parsers.cisco import CiscoShowVersionParser
        ver_data = CiscoShowVersionParser(raw_string=version_output, platform_slug=slug).get_facts()
        
        current_version = ver_data.get('version')
        if not current_version:
            # Fallback if structured parser fails but textual match is present
            if target_version in version_output.lower():
                report_output += f"Device Running Version: MATCH (Textual fallback)\n"
                report_output += f"VERIFICATION PASSED: Version matches target ({target_version}).\n"
                return True, report_output
                
            report_output += "Failed to structurally parse version from device output.\n"
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


class CiscoVerifyScrapli(ScrapliTask, CiscoVerifyLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        try:
            with self.connect(device) as conn:
                result = conn.send_command("show version", timeout_ops=30)
                return self._evaluate_verification(device, target_image, result.result)
        except Exception as e:
            logger.error(f"[Verification Scrapli] {device.name}: {e}")
            return False, f"Verification connection error: {e}"

class CiscoVerifyNetmiko(NetmikoTask, CiscoVerifyLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        try:
            with self.connect(device) as conn:
                output = conn.send_command("show version", read_timeout=30)
                return self._evaluate_verification(device, target_image, output)
        except Exception as e:
            logger.error(f"[Verification Netmiko] {device.name}: {e}")
            return False, f"Verification connection error: {e}"

class CiscoVerifyUnicon(UniconTask, CiscoVerifyLogicMixin):
    """
    Post-Activation Version Verification.
    Connects to the device, retrieves the current running firmware version,
    and compares it to the Job's target_image.version via CiscoShowVersionParser.
    """
    
    # Define which device platforms support verification using Unicon
    SUPPORTED_PLATFORMS = ['ios', 'iosxe', 'nxos']

    def execute(self, device, target_image=None, **kwargs):
        os_type = "iosxe"
        if hasattr(device, 'platform') and device.platform:
            os_type = getattr(device.platform, 'slug', 'iosxe')
            
        if os_type not in self.SUPPORTED_PLATFORMS:
            return False, f"Verification not supported for platform '{os_type}'. Supported: {', '.join(self.SUPPORTED_PLATFORMS)}"

        try:
            with self.connect(device, connection_timeout=60) as pyats_device:
                output = pyats_device.execute('show version')
                return self._evaluate_verification(device, target_image, output)
        except Exception as e:
            logger.error(f"[Verification Unicon] {device.name}: {e}")
            return False, f"Verification connection error: {str(e)}"
