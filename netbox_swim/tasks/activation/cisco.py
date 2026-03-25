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
    
    Supports both modes:
      - INSTALL mode: install add file <path> activate commit
      - BUNDLE mode:  boot system <path> → write memory → reload
    
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
            # 1. Detect current mode (informational — does not block execution)
            mode = "UNKNOWN"
            try:
                version_out = pyats_device.execute("show version | include Mode")
                if "INSTALL" in version_out:
                    mode = "INSTALL"
                elif "BUNDLE" in version_out:
                    mode = "BUNDLE"
                logger.info(f"[Activation] {device.name} running in {mode} mode")
            except Exception as e:
                logger.warning(f"[Activation] Could not detect mode for {device.name}: {e}")

            from unicon.eal.dialogs import Dialog, Statement

            # 2. Execute based on detected mode
            if mode == "INSTALL":
                return self._activate_install_mode(pyats_device, dest_path, file_name)
            else:
                # BUNDLE mode or UNKNOWN — use traditional boot system approach
                return self._activate_bundle_mode(pyats_device, dest_path, file_name, mode)

    def _activate_install_mode(self, pyats_device, dest_path, file_name):
        """INSTALL mode: install add file <path> activate commit"""
        from unicon.eal.dialogs import Dialog, Statement

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
                return [("FAIL", f"INSTALL mode activation failed: {out[-500:]}")]
            return [("PASS", f"INSTALL mode activation initiated. "
                     f"Device will reload with {file_name}.")]
        except Exception as e:
            err_str = str(e).lower()
            if 'timeout' in err_str or 'disconnect' in err_str or 'eof' in err_str:
                return [("PASS", f"INSTALL mode activation initiated. "
                         f"Device is reloading (connection dropped as expected).")]
            return [("FAIL", f"INSTALL mode activation exception: {str(e)}")]

    def _activate_bundle_mode(self, pyats_device, dest_path, file_name, mode):
        """BUNDLE/UNKNOWN mode: no boot system → boot system <path> → write memory → reload"""
        from unicon.eal.dialogs import Dialog, Statement

        try:
            # Set boot variable
            pyats_device.configure([
                "no boot system",
                f"boot system {dest_path}"
            ], timeout=30)
        except Exception as e:
            return [("FAIL", f"{mode} mode: Failed to set boot variable: {str(e)}")]

        # Save config
        try:
            pyats_device.execute("write memory", timeout=60)
        except Exception as e:
            return [("FAIL", f"{mode} mode: Failed to save config (write memory): {str(e)}")]

        # Verify boot variable was set correctly
        try:
            boot_out = pyats_device.execute("show boot", timeout=30)
            if file_name not in boot_out:
                return [("FAIL", f"{mode} mode: Boot variable verification failed. "
                         f"Expected '{file_name}' in show boot output: {boot_out[:300]}")]
        except Exception as e:
            logger.warning(f"Could not verify boot variable: {e}")

        # Reload
        dialog = Dialog([
            Statement(
                pattern=r'System configuration has been modified.*\[yes/no\]',
                action='sendline(yes)', loop_continue=True
            ),
            Statement(
                pattern=r'Proceed with reload\? \[confirm\]',
                action='sendline()', loop_continue=True
            ),
            Statement(
                pattern=r'\[confirm\]',
                action='sendline()', loop_continue=True
            ),
        ])

        try:
            pyats_device.execute("reload", timeout=120, reply=dialog)
            return [("PASS", f"{mode} mode activation complete. "
                     f"Boot variable set to {dest_path}. Device is reloading.")]
        except Exception as e:
            err_str = str(e).lower()
            if 'timeout' in err_str or 'disconnect' in err_str or 'eof' in err_str:
                return [("PASS", f"{mode} mode activation complete. "
                         f"Device is reloading (connection dropped as expected).")]
            return [("FAIL", f"{mode} mode reload exception: {str(e)}")]
