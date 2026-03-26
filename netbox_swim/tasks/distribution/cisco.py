import re
import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask

logger = logging.getLogger('netbox_swim')

# Platforms with implemented distribution support
SUPPORTED_OS_FAMILIES = {'iosxe', 'ios'}


class CiscoDistributeScrapli(ScrapliTask):
    def execute(self, device, target_image=None, **kwargs):
        return [("FAIL", "Scrapli distribution is not yet implemented. "
                 "Set connection_priority to 'unicon' in your Hardware Group.")]


class CiscoDistributeNetmiko(NetmikoTask):
    def execute(self, device, target_image=None, **kwargs):
        return [("FAIL", "Netmiko distribution is not yet implemented. "
                 "Set connection_priority to 'unicon' in your Hardware Group.")]


class CiscoDistributeUnicon(UniconTask):
    """
    Distributes firmware to Cisco IOS/IOS-XE devices.
    
    Supported platforms: IOS, IOS-XE
    NX-OS, EOS, Junos: Not yet implemented (will abort cleanly).
    
    Protocol support is extensible via the dispatch pattern:
      - To add SCP:  implement _build_copy_cmd_scp()
      - To add TFTP: implement _build_copy_cmd_tftp()
      - To add SFTP: implement _build_copy_cmd_sftp()
    Then add the protocol name to SUPPORTED_PROTOCOLS.
    """
    
    # -------------------------------------------------------
    # Protocol Registry — add new protocols here
    # -------------------------------------------------------
    SUPPORTED_PROTOCOLS = {'http', 'https'}
    
    def _resolve_os_family(self, device):
        """Resolve OS family from PLATFORM_MAPPINGS."""
        from ...constants import PLATFORM_MAPPINGS
        slug = getattr(device.platform, 'slug', 'default')
        mapping = PLATFORM_MAPPINGS.get(slug, PLATFORM_MAPPINGS.get('default', {}))
        genie_os = mapping.get('genie', 'iosxe')
        if genie_os in ('ios', 'iosxe'):
            return 'iosxe'
        return genie_os

    # -------------------------------------------------------
    # Copy Command Builders — one per protocol
    # -------------------------------------------------------
    # To add a new protocol (e.g., SCP), simply:
    #   1. Add 'scp' to SUPPORTED_PROTOCOLS above
    #   2. Implement _build_copy_cmd_scp() below
    #   That's it — execute() will auto-dispatch.
    
    def _build_copy_cmd_http(self, fs, file_name, dest_path):
        """Build IOS copy command for HTTP/HTTPS transfers."""
        protocol = fs.protocol.lower()
        auth_str = f"{fs.username}:{fs.password}@" if fs.username else ""
        port_str = f":{fs.port}" if fs.port else ""
        base_path = f"{fs.base_path.strip('/')}/" if fs.base_path else ""
        return f"copy {protocol}://{auth_str}{fs.ip_address}{port_str}/{base_path}{file_name} {dest_path}"
    
    # Alias — HTTPS uses same syntax as HTTP
    _build_copy_cmd_https = _build_copy_cmd_http
    
    # ----- FUTURE: Uncomment and implement when needed -----
    #
    # def _build_copy_cmd_scp(self, fs, file_name, dest_path):
    #     """Build IOS copy command for SCP transfers."""
    #     auth_str = f"{fs.username}@" if fs.username else ""
    #     base_path = f"{fs.base_path.strip('/')}/" if fs.base_path else ""
    #     return f"copy scp://{auth_str}{fs.ip_address}/{base_path}{file_name} {dest_path}"
    #
    # def _build_copy_cmd_tftp(self, fs, file_name, dest_path):
    #     """Build IOS copy command for TFTP transfers."""
    #     base_path = f"{fs.base_path.strip('/')}/" if fs.base_path else ""
    #     return f"copy tftp://{fs.ip_address}/{base_path}{file_name} {dest_path}"
    #
    # def _build_copy_cmd_sftp(self, fs, file_name, dest_path):
    #     """Build IOS copy command for SFTP transfers."""
    #     auth_str = f"{fs.username}@" if fs.username else ""
    #     base_path = f"{fs.base_path.strip('/')}/" if fs.base_path else ""
    #     return f"copy sftp://{auth_str}{fs.ip_address}/{base_path}{file_name} {dest_path}"
    #
    # Then add to SUPPORTED_PROTOCOLS: {'http', 'https', 'scp', 'tftp', 'sftp'}
    # -------------------------------------------------------

    def _get_copy_command(self, protocol, fs, file_name, dest_path):
        """Dispatch to the correct protocol builder method."""
        method_name = f"_build_copy_cmd_{protocol}"
        builder = getattr(self, method_name, None)
        if not builder:
            return None, f"Protocol '{protocol}' has no command builder. Implement {method_name}()."
        return builder(fs, file_name, dest_path), None

    # -------------------------------------------------------
    # Main Execution
    # -------------------------------------------------------
    def execute(self, device, target_image=None, **kwargs):
        if not target_image:
            return [("FAIL", "No target image assigned. Cannot distribute.")]
        
        # --- Platform gate ---
        os_family = self._resolve_os_family(device)
        if os_family not in SUPPORTED_OS_FAMILIES:
            return [("FAIL", f"Distribution for '{os_family.upper()}' platform is not yet implemented. "
                     f"Currently supported: IOS, IOS-XE only. "
                     f"Device '{device.name}' upgrade aborted at distribution stage.")]
        
        # --- Resolve file server candidates (with fallback chain) ---
        from ...models import FileServer
        
        candidates = []
        # Explicit FK on image is always first candidate (backward-compatible)
        if target_image.file_server:
            candidates.append(target_image.file_server)
        
        # Append regional/hierarchy candidates from resolver
        resolved = FileServer.resolve_for_device(device)
        for fs in resolved:
            if fs.pk not in {c.pk for c in candidates}:
                candidates.append(fs)
        
        if not candidates:
            return [("FAIL", f"No file server found for device '{device.name}'. "
                     f"Either assign a File Server to the Software Image, "
                     f"or configure regional/default file servers with matching hierarchy.")]
        
        # --- Pre-compute reusable values ---
        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"
        expected_size = getattr(target_image, 'file_size_bytes', None)
        expected_md5 = getattr(target_image, 'hash_md5', None) or ""
        
        tacacs_intf = (device.custom_field_data.get('tacacs_interface') 
                       or device.custom_field_data.get('tacacs_source_interface'))
        
        # --- Connect once, try each server ---
        with self.connect(device, connection_timeout=300) as pyats_device:
            
            # 1. Pre-check: skip transfer if file already exists with correct size + MD5
            if expected_size:
                try:
                    result = pyats_device.execute(f"dir {dest_path}", timeout=30)
                    match = re.search(r'\s+(\d+)\s+\w{3}\s+\d+', result)
                    if match and int(match.group(1)) == expected_size:
                        if expected_md5:
                            verify_out = pyats_device.execute(
                                f"verify /md5 {dest_path} {expected_md5}", timeout=600
                            )
                            if "Verified" in verify_out:
                                return [("PASS", f"File '{file_name}' already exists on "
                                         f"{boot_drive} with matching MD5. Skipping transfer.")]
                        else:
                            return [("PASS", f"File '{file_name}' already exists on "
                                     f"{boot_drive} with matching size ({expected_size} bytes). "
                                     f"Skipping transfer (no MD5 configured for verification).")]
                except Exception:
                    pass  # File doesn't exist yet — proceed with transfer
            
            # 2. Setup Unicon dialog handler for interactive copy prompts
            from unicon.eal.dialogs import Dialog, Statement
            dialog = Dialog([
                Statement(
                    pattern=r'Destination filename \[.*\]\?',
                    action='sendline()', loop_continue=True
                ),
                Statement(
                    pattern=r'Do you want to over write\? \[confirm\]',
                    action='sendline()', loop_continue=True
                ),
                Statement(
                    pattern=r'\[confirm\]',
                    action='sendline()', loop_continue=True
                ),
                Statement(
                    pattern=r'Address or name of remote host',
                    action='sendline()', loop_continue=True
                ),
                Statement(
                    pattern=r'%Error|TFTP .*error|Connection refused|No such file',
                    action=None, loop_continue=False
                ),
                Statement(
                    pattern=r'(?i)timed out|(?i)connection timed out',
                    action=None, loop_continue=False
                ),
            ])

            # 3. Try each file server candidate in order
            all_errors = []
            for fs_idx, fs in enumerate(candidates, start=1):
                fs_label = f"{fs.name} ({fs.ip_address})"
                
                # --- Protocol check for this server ---
                protocol = fs.protocol.lower() if fs.protocol else 'http'
                if protocol not in self.SUPPORTED_PROTOCOLS:
                    all_errors.append(f"[{fs_label}] Protocol '{protocol}' not supported, skipping.")
                    continue
                
                # --- Build copy command ---
                cmd, error = self._get_copy_command(protocol, fs, file_name, dest_path)
                if error:
                    all_errors.append(f"[{fs_label}] {error}")
                    continue
                
                # --- Configure HTTP client source interface (VRF routing) ---
                if tacacs_intf and protocol in ('http', 'https'):
                    try:
                        pyats_device.configure(
                            f"ip http client source-interface {tacacs_intf}", timeout=30
                        )
                    except Exception as e:
                        all_errors.append(f"[{fs_label}] Failed to set HTTP source-interface: {str(e)}")
                        continue
                
                # --- File transfer with retry (max 2 attempts per server) ---
                max_attempts = 2
                success = False
                last_err = ""
                
                try:
                    pyats_device.default.log_stdout = False
                except Exception:
                    pass

                for attempt in range(1, max_attempts + 1):
                    try:
                        result = pyats_device.execute(cmd, timeout=7200, reply=dialog)
                        if 'bytes copied' in result.lower() or 'OK' in result:
                            success = True
                            break
                        else:
                            last_err = f"Attempt {attempt} output: {result[-500:]}"
                    except Exception as e:
                        last_err = f"Attempt {attempt} exception: {str(e)}"
                        if attempt < max_attempts:
                            import time
                            time.sleep(10)
                        
                try:
                    pyats_device.default.log_stdout = True
                except Exception:
                    pass
                
                if success:
                    # 4. Post-transfer MD5 verification
                    if expected_md5:
                        try:
                            verify_out = pyats_device.execute(
                                f"verify /md5 {dest_path} {expected_md5}", timeout=600
                            )
                            if "Verified" not in verify_out:
                                return [("FAIL", f"Post-download MD5 verification FAILED for "
                                         f"'{file_name}'. Output: {verify_out}")]
                        except Exception as e:
                            return [("FAIL", f"MD5 verification command failed: {str(e)}")]
                    
                    fallback_note = ""
                    if fs_idx > 1:
                        fallback_note = f" (fallback #{fs_idx}, tried {fs_idx - 1} server(s) first)"
                    return [("PASS", f"Successfully distributed '{file_name}' to {boot_drive} "
                             f"via {fs_label}{fallback_note}")]
                else:
                    all_errors.append(f"[{fs_label}] Transfer failed: {last_err}")
                    logger.warning(f"Distribution: File server {fs_label} failed for "
                                   f"device {device.name}, trying next candidate...")
            
            # All candidates exhausted
            error_summary = "\n".join(all_errors)
            return [("FAIL", f"Distribution failed — exhausted all {len(candidates)} file server(s).\n"
                     f"Errors:\n{error_summary}")]

