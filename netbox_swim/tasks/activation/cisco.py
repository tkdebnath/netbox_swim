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
    Activates firmware on Cisco Catalyst 9300 series.
    
    Uses: install add file <path> activate commit
    Works for both INSTALL and BUNDLE mode (converts BUNDLE → INSTALL).
    
    Supported: Catalyst 9300.
    Not yet supported: Other Catalyst models, NX-OS, EOS.
    """

    def execute(self, device, target_image=None, **kwargs):
        if not target_image:
            return [("FAIL", "No target image assigned. Cannot activate.")]

        # Hard lock: Only Catalyst 9300 supported for now
        model = getattr(getattr(device, 'device_type', None), 'model', '').upper()
        if '9300' not in model:
            return [("FAIL", f"Activation is currently only supported for Catalyst 9300 series. "
                     f"Device model '{model}' is not yet implemented. "
                     f"Upgrade aborted at activation stage.")]

        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"

        with self.connect(device, connection_timeout=60) as pyats_device:
            from unicon.eal.dialogs import Dialog, Statement

            # 1. Detect current mode (informational only — logged, not gating)
            try:
                version_out = pyats_device.execute("show version | include Mode")
                if "INSTALL" in version_out:
                    logger.info(f"[Activation] {device.name} running in INSTALL mode")
                elif "BUNDLE" in version_out:
                    logger.info(f"[Activation] {device.name} running in BUNDLE mode — will convert to INSTALL")
                else:
                    logger.info(f"[Activation] {device.name} mode detection: {version_out.strip()}")
            except Exception as e:
                logger.warning(f"[Activation] Could not detect mode for {device.name}: {e}")

            # 2. Configure boot parameters (hardening)
            try:
                config_cmd = [
                    "no boot system",
                    "boot system flash:packages.conf",
                    "no boot manual",
                    "no system ignore startupconfig switch all",
                ]
                pyats_device.configure(config_cmd, timeout=30)
            except Exception as e:
                logger.warning(f"Boot configuration warning: {e}")

            # 3. Save config
            try:
                save_dialog = Dialog([
                    Statement(
                        pattern=r'Destination filename \[startup-config\]\?',
                        action='sendline()', loop_continue=False, continue_timer=False
                    ),
                ])
                pyats_device.execute(
                    "copy running-config startup-config", timeout=60, reply=save_dialog
                )
            except Exception as e:
                logger.warning(f"Config save warning: {e}")

            # 4. Run install command (works for both INSTALL and BUNDLE mode)
            cmd = f"install add file {dest_path} activate commit"

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
                    return [("FAIL", f"Activation failed: {out[-500:]}")]
                return [("PASS", f"Activation initiated. Device will reload with {file_name}.")]
            except Exception as e:
                err_str = str(e).lower()
                if 'timeout' in err_str or 'disconnect' in err_str or 'eof' in err_str:
                    return [("PASS", f"Activation initiated. "
                             f"Device is reloading (connection dropped as expected).")]
                return [("FAIL", f"Activation exception: {str(e)}")]
