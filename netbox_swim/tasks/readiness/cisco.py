from ..base import ScrapliTask, NetmikoTask, UniconTask
import logging

logger = logging.getLogger('netbox_swim')


class CiscoReadinessLogicMixin:
    """
    Houses the vendor-specific Business Logic for evaluating Readiness.
    Platform-aware: adapts commands and evaluation per OS family
    (IOS-XE, NX-OS, EOS, Junos).
    """

    def _resolve_os_family(self, device):
        """Resolve the OS family from PLATFORM_MAPPINGS for platform-specific logic."""
        from ...constants import PLATFORM_MAPPINGS
        slug = getattr(device.platform, 'slug', 'default')
        mapping = PLATFORM_MAPPINGS.get(slug, PLATFORM_MAPPINGS.get('default', {}))
        genie_os = mapping.get('genie', 'iosxe')

        if genie_os in ('ios', 'iosxe'):
            return 'iosxe'
        elif genie_os == 'nxos':
            return 'nxos'
        elif genie_os == 'junos':
            return 'junos'
        elif genie_os == 'eos':
            return 'eos'
        else:
            return genie_os

    def _get_readiness_commands(self, device, target_image):
        """
        Returns a dict of command_key -> CLI command, tailored per platform.
        Each platform only gets the commands that are valid for it.
        """
        os_family = self._resolve_os_family(device)
        boot_drive = self._get_boot_drive(device, target_image)

        # Universal commands
        commands = {
            'flash': f"dir {boot_drive}",
            'version': "show version",
        }

        # Platform-specific additions
        if os_family == 'iosxe':
            commands['romvar'] = "show romvar"
        elif os_family == 'nxos':
            commands['boot'] = "show boot"
            commands['flash'] = f"dir {boot_drive}"
        elif os_family == 'junos':
            commands['flash'] = "show system storage"
            commands['version'] = "show version"
        elif os_family == 'eos':
            commands['flash'] = "dir flash:"
            commands['boot'] = "show boot-config"

        return commands

    def _evaluate_readiness(self, device, target_image, command_outputs):
        """
        Evaluate readiness based on collected command outputs.
        command_outputs: dict of command_key -> raw_output_string
        """
        logs = []
        is_ready = True
        os_family = self._resolve_os_family(device)
        slug = getattr(device.platform, 'slug', 'cisco_ios')

        logs.append(("info", f"OS Family: {os_family.upper()} | Platform: {slug}"))

        # --- Parse Flash Storage ---
        flash_output = command_outputs.get('flash', '')
        if flash_output:
            from netbox_swim.parsers.cisco import CiscoDirFlashParser
            flash_data = CiscoDirFlashParser(raw_string=flash_output, platform_slug=slug).get_facts()
        else:
            flash_data = {'total_bytes': 0, 'free_bytes': 0, 'total_mb': 0.0, 'free_mb': 0.0}

        # --- Parse Version ---
        version_output = command_outputs.get('version', '')
        if version_output:
            from netbox_swim.parsers.cisco import CiscoShowVersionParser
            ver_data = CiscoShowVersionParser(raw_string=version_output, platform_slug=slug).get_facts()
        else:
            ver_data = {}

        # --- Context Assembly ---
        image_name = target_image.image_name if target_image else "UNKNOWN"
        image_size = target_image.file_size_bytes if target_image and target_image.file_size_bytes else 0
        img_mb = image_size / 1024 / 1024 if image_size else 0
        target_version = target_image.version if target_image else "UNKNOWN"

        logs.append(("info", "---------- Readiness Context ----------"))
        logs.append(("info", f"Target Image Name: {image_name}"))
        logs.append(("info", f"Target Image Size: {img_mb:.2f} MB"))

        # -------------------------------------------------------
        # 1. Evaluate Flash Storage (universal)
        # -------------------------------------------------------
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
                logs.append(("success", "Sufficient flash space available."))
            else:
                logs.append(("error", f"INSUFFICIENT FLASH SPACE. Cannot accommodate {req_mb:.2f} MB."))
                is_ready = False
        else:
            logs.append(("warning", "Could not parse Total/Free space from flash output. Validation bypassed."))

        # -------------------------------------------------------
        # 2. Platform-Specific Boot/Config Validation
        # -------------------------------------------------------
        logs.append(("info", "--------- Config Validation ----------"))

        if os_family == 'iosxe':
            # IOS-XE: Check romvar for startup config override
            romvar_output = command_outputs.get('romvar', '')
            if romvar_output:
                from netbox_swim.parsers.cisco import CiscoRomvarParser
                rom_data = CiscoRomvarParser(raw_string=romvar_output, platform_slug=slug).get_facts()
                if not rom_data['is_startup_ignored']:
                    logs.append(("success", "Startup config NOT ignored (Expected)"))
                else:
                    logs.append(("warning", "Startup config is currently ignored in Romvar."))
            else:
                logs.append(("warning", "Romvar output unavailable. Startup config validation skipped."))

        elif os_family == 'nxos':
            # NX-OS: Check boot variable is set
            boot_output = command_outputs.get('boot', '')
            if boot_output:
                if 'BOOT variable' in boot_output or 'sup-1' in boot_output or 'bootflash' in boot_output:
                    logs.append(("info", f"NX-OS Boot Config:\n{boot_output[:300]}"))
                    logs.append(("success", "Boot configuration present."))
                else:
                    logs.append(("warning", "No boot variable detected in NX-OS boot config."))
            else:
                logs.append(("warning", "Boot output unavailable. NX-OS boot validation skipped."))

        elif os_family == 'eos':
            # Arista EOS: Check boot-config
            boot_output = command_outputs.get('boot', '')
            if boot_output:
                logs.append(("info", f"EOS Boot Config:\n{boot_output[:300]}"))
                logs.append(("success", "Boot configuration retrieved."))
            else:
                logs.append(("warning", "EOS boot validation skipped — no output available."))

        elif os_family == 'junos':
            logs.append(("info", "Junos does not require romvar/boot validation. Skipped."))

        else:
            logs.append(("info", f"No platform-specific config checks for OS family: {os_family}"))

        # -------------------------------------------------------
        # 3. Version Compatibility (universal)
        # -------------------------------------------------------
        logs.append(("info", "-------- Version Validation ----------"))

        current_version = ver_data.get('version') or "UNKNOWN"
        logs.append(("info", f"Current Running Version: {current_version}"))
        logs.append(("info", f"Target Firmware Version: {target_version}"))

        if target_image:
            if target_version == current_version or target_version in version_output:
                logs.append(("error", "VERSION COLLISION: Device is already running the Target Version. Upgrade is redundant."))
                is_ready = False
            else:
                logs.append(("success", "Version Compatibility certified! Device is operating outside target version."))
        else:
            logs.append(("warning", "No target image assigned for precise version compliance."))

        # -------------------------------------------------------
        # 4. Summary
        # -------------------------------------------------------
        logs.append(("info", "--------- Execution Summary ----------"))
        if is_ready:
            logs.append(("pass", "Hardware Readiness Checks PASSED! Device cleared for Deployment."))
        else:
            logs.append(("failed", "Hardware Readiness Checks FAILED! Upgrade Aborted."))

        return logs


class ReadinessCiscoScrapli(ScrapliTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        commands = self._get_readiness_commands(device, target_image)
        outputs = {}

        with self.connect(device) as conn:
            for key, cmd in commands.items():
                try:
                    result = conn.send_command(cmd, timeout_ops=30)
                    outputs[key] = result.result
                except Exception as e:
                    outputs[key] = ""
                    logger.warning(f"Readiness command '{cmd}' failed on {device.name}: {e}")

        return self._evaluate_readiness(device, target_image, outputs)


class ReadinessCiscoNetmiko(NetmikoTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        commands = self._get_readiness_commands(device, target_image)
        outputs = {}

        with self.connect(device) as conn:
            for key, cmd in commands.items():
                try:
                    outputs[key] = conn.send_command(cmd, read_timeout=30)
                except Exception as e:
                    outputs[key] = ""
                    logger.warning(f"Readiness command '{cmd}' failed on {device.name}: {e}")

        return self._evaluate_readiness(device, target_image, outputs)


class ReadinessCiscoUnicon(UniconTask, CiscoReadinessLogicMixin):
    def execute(self, device, target_image=None, auto_update=False):
        commands = self._get_readiness_commands(device, target_image)
        outputs = {}

        with self.connect(device, connection_timeout=60) as pyats_device:
            for key, cmd in commands.items():
                try:
                    outputs[key] = pyats_device.execute(cmd, timeout=30)
                except Exception as e:
                    outputs[key] = ""
                    logger.warning(f"Readiness command '{cmd}' failed on {device.name}: {e}")

        return self._evaluate_readiness(device, target_image, outputs)
