import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask

logger = logging.getLogger('netbox_swim')


class CiscoActivateScrapli(ScrapliTask):
    def execute(self, device, target_image=None, **kwargs):
        return [("FAIL", "Scrapli activation is not yet implemented. "
                 "Set connection_priority to 'unicon' in your Hardware Group.")]


class CiscoActivateNetmiko(NetmikoTask):
    def execute(self, device, target_image=None, **kwargs):
        return [("FAIL", "Netmiko activation is not yet implemented. "
                 "Set connection_priority to 'unicon' in your Hardware Group.")]


class CiscoActivateUnicon(UniconTask):
    """
    Activates firmware on Cisco Catalyst 9300 series (INSTALL mode only).
    
    Runs: install add file <path> activate commit
    
    Supported: Catalyst 9300 in INSTALL mode.
    Not yet supported: BUNDLE mode, other Catalyst models, NX-OS, EOS.
    """

    def execute(self, device, target_image=None, **kwargs):
        if not target_image:
            return [("FAIL", "No target image assigned. Cannot activate.")]

        # Hard lock: Only Catalyst 9300 INSTALL mode supported for now
        model = getattr(getattr(device, 'device_type', None), 'model', '').upper()
        if '9300' not in model:
            return [("FAIL", f"Activation is currently only supported for Catalyst 9300 series. "
                     f"Device model '{model}' is not yet implemented. "
                     f"Upgrade aborted at activation stage.")]

        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"

        with self.connect(device, connection_timeout=60) as pyats_device:
            # 1. Check if device is running in INSTALL mode
            try:
                version_out = pyats_device.execute("show version | include Mode")
            except Exception as e:
                return [("FAIL", f"Failed to check device mode: {str(e)}")]

            if "INSTALL" not in version_out:
                return [("FAIL", f"Device is NOT in INSTALL mode. "
                         f"BUNDLE mode activation is not yet implemented. "
                         f"Current mode: {version_out.strip()}")]

            # 2. INSTALL mode activation (Cat9k: install add file ... activate commit)
            cmd = f"install add file {dest_path} activate commit"

            from unicon.eal.dialogs import Dialog, Statement
            dialog = Dialog([
                Statement(
                    pattern=r'This operation may require a reload of the system.*\[y/n\]',
                    action='sendline(y)', loop_continue=True
                ),
                Statement(
                    pattern=r'\[y/n\]',
                    action='sendline(y)', loop_continue=True
                ),
                Statement(
                    pattern=r'Do you want to proceed with reload\?',
                    action='sendline(y)', loop_continue=True
                ),
            ])

            try:
                out = pyats_device.execute(cmd, timeout=3600, reply=dialog)
                if "%Error" in out or "FAILED" in out:
                    return [("FAIL", f"INSTALL mode activation failed: {out[-500:]}")]
                return [("PASS", f"INSTALL mode activation initiated. "
                         f"Device will reload with {file_name}.")]
            except Exception as e:
                # Connection drop during reload is expected behavior
                err_str = str(e).lower()
                if 'unicon' in err_str and ('timeout' in err_str or 'disconnect' in err_str or 'eof' in err_str):
                    return [("PASS", f"INSTALL mode activation initiated. "
                             f"Device is reloading (connection dropped as expected).")]
                return [("FAIL", f"INSTALL mode activation exception: {str(e)}")]
