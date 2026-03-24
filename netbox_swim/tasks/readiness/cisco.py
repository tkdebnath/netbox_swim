from ..base import ScrapliTask, NetmikoTask, UniconTask
import re
from netbox_swim.parsers.cisco import CiscoDirFlashParser, CiscoRomvarParser, CiscoShowVersionParser

class CiscoReadinessLogicMixin:
    """
    Houses the vendor-specific Business Logic for evaluating Readiness.
    """
    def _evaluate_readiness(self, device, target_image, flash_output, romvar_output, version_output):
        logs = []
        is_ready = True
        
        # --- Instantiate Parsers ---
        slug = getattr(device.platform, 'slug', 'cisco_ios')
        
        logs.append(("info", f"Executing Parsers for {slug}..."))
        flash_data = CiscoDirFlashParser(raw_string=flash_output, platform_slug=slug).get_facts()
        rom_data = CiscoRomvarParser(raw_string=romvar_output, platform_slug=slug).get_facts()
        ver_data = CiscoShowVersionParser(raw_string=version_output, platform_slug=slug).get_facts()
        
        # --- Context Assembly ---
        image_name = target_image.image_name if target_image else "UNKNOWN"
        image_size = target_image.file_size_bytes if target_image and target_image.file_size_bytes else 0
        img_mb = image_size / 1024 / 1024 if image_size else 0
        target_version = target_image.version if target_image else "UNKNOWN"
        
        logs.append(("info", "---------- Readiness Context ----------"))
        logs.append(("info", f"Target Image Name: {image_name}"))
        logs.append(("info", f"Target Image Size: {img_mb:.2f} MB"))
        
        # 1. Evaluate Flash Storage
        logs.append(("info", "---------- Storage Validation --------"))
        required_space = image_size * 2.5 if image_size else 0
        req_mb = required_space / 1024 / 1024
        
        total_mb = flash_data['total_mb']
        free_mb = flash_data['free_mb']
        free_bytes = flash_data['free_bytes']
        
        if total_mb > 0:
            logs.append(("info", f"Total Flash Space: {total_mb:.2f} MB"))
            logs.append(("info", f"Available Flash Space: {free_mb:.2f} MB"))
            logs.append(("info", f"Required Upgrade Clear Space (~2.5x): {req_mb:.2f} MB"))
            
            if free_bytes > required_space:
                logs.append(("success", f"Sufficient flash space available."))
            else:
                logs.append(("error", f"INSUFFICIENT FLASH SPACE. Cannot accommodate {req_mb:.2f} MB."))
                is_ready = False
        else:
            logs.append(("warning", "Could not parse Total/Free space from hardware flash output. Validation bypassed."))

        # 2. Evaluate Startup Config
        logs.append(("info", "--------- Config Validation ----------"))
        if not rom_data['is_startup_ignored']:
            logs.append(("success", "Startup config NOT ignored (Expected)"))
        else:
            logs.append(("warning", "Startup config is currently ignored in Romvar."))
            
        # 3. Evaluate Version Compatibility
        logs.append(("info", "-------- Version Validation ----------"))
        
        current_version = ver_data.get('version') or "UNKNOWN"
        logs.append(("info", f"Current Running Version: {current_version}"))
        logs.append(("info", f"Target Firmware Version: {target_version}"))
        
        if target_image:
            if target_version == current_version or target_version in version_output:
                logs.append(("error", "VERSION COLLISION: Hardware is already running the Target Version. Upgrade is redundant and aborted."))
                is_ready = False
            else:
                logs.append(("success", "Version Compatibility certified! Device is operating linearly outside target version restrictions."))
        else:
            logs.append(("warning", "No target image assigned for precise version compliance."))
            
        logs.append(("info", "--------- Execution Summary ----------"))
        if is_ready:
            logs.append(("pass", "Hardware Readiness Checks PASSED! Device cleared for Deployment."))
        else:
            logs.append(("failed", "Hardware Readiness Checks FAILED! Upgrade Aborted."))
            
        return logs

class ReadinessCiscoScrapli(ScrapliTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        raise NotImplementedError("Scrapli readiness check is pending future implementation.")

class ReadinessCiscoNetmiko(NetmikoTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        raise NotImplementedError("Netmiko readiness check is pending future implementation.")

class ReadinessCiscoUnicon(UniconTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        boot_drive = self._get_boot_drive(device, target_image)
        
        with self.connect(device, connection_timeout=60) as pyats_device:
            try:
                flash_output = pyats_device.execute(f"dir {boot_drive}", timeout=30)
            except Exception as e:
                return [("FAIL", f"Failed to retrieve flash info: {e}")]
                
            try:
                romvar_output = pyats_device.execute("show romvar", timeout=30)
            except Exception as e:
                return [("FAIL", f"Failed to retrieve romvar info: {e}")]
                
            try:
                version_output = pyats_device.execute("show version", timeout=30)
            except Exception as e:
                return [("FAIL", f"Failed to retrieve version info: {e}")]
                
            return self._evaluate_readiness(device, target_image, flash_output, romvar_output, version_output)
