import re
from unicon.eal.dialogs import Dialog, Statement
from ..base import ScrapliTask, NetmikoTask, UniconTask

class CiscoDistributeLogicMixin:
    """Provides generic methods to distribute firmware to Cisco IOS/IOS-XE."""
    
    def _execute_file_transfer(self, device, target_image):
        if not target_image:
            return "[SKIP] No target image assigned."
        fs = target_image.file_server
        if not fs:
            raise ValueError(f"Target SoftwareImage '{target_image.image_name}' is not assigned to a FileServer.")
            
        boot_drive = self._get_boot_drive(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"

        # Standard Cisco IOS copy syntax
        cmd = f"copy {fs.protocol}://{fs.username}:{fs.password}@{fs.ip_address}/{fs.base_path}/{file_name} {dest_path}"
        
        return self._handle_interactive_copy(cmd, dest_path)

    def _handle_interactive_copy(self, cmd, dest_path):
        raise NotImplementedError


class CiscoDistributeScrapli(ScrapliTask, CiscoDistributeLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Scrapli distribution is pending future implementation.")


class CiscoDistributeNetmiko(NetmikoTask, CiscoDistributeLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Netmiko distribution is pending future implementation.")


class CiscoDistributeUnicon(UniconTask, CiscoDistributeLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        if not target_image:
            return [("SKIP", "No target image assigned.")]
            
        fs = target_image.file_server
        if not fs:
            raise ValueError(f"Target SoftwareImage '{target_image.image_name}' is not assigned to a FileServer.")
            
        protocol = fs.protocol.lower() if fs.protocol else 'http'
        if protocol != 'http':
            raise NotImplementedError(f"Protocol '{protocol}' is marked for future implementation. Currently only HTTP is supported.")
            
        boot_drive = getattr(self, '_get_boot_drive', lambda d, t: 'flash:/')(device, target_image)
        file_name = target_image.image_file_name
        dest_path = f"{boot_drive}{file_name}"
        
        # HTTP specific path format for IOS copy
        auth_str = f"{fs.username}:{fs.password}@" if fs.username else ""
        port_str = f":{fs.port}" if fs.port else ""
        base_path = f"{fs.base_path.strip('/')}/" if fs.base_path else ""

        cmd = f"copy {protocol}://{auth_str}{fs.ip_address}{port_str}/{base_path}{file_name} {dest_path}"
        
        expected_size = getattr(target_image, 'file_size_bytes', None)
        expected_md5 = getattr(target_image, 'hash_md5', None)
        
        tacacs_intf = device.custom_field_data.get('tacacs_interface') or device.custom_field_data.get('tacacs_source_interface')
        
        with self.connect(device, connection_timeout=300) as pyats_device:
            # Re-used logic for configuring HTTP client source interface
            if tacacs_intf:
                try:
                    pyats_device.configure(f"ip http client source-interface {tacacs_intf}", timeout=30)
                except Exception as e:
                    return [("FAIL", f"Failed to push ip http client config using tacacs interface {tacacs_intf}: {str(e)}")]
            
            # 1. Pre-Check existing file
            if expected_size:
                try:
                    result = pyats_device.execute(f"dir {dest_path}", timeout=30)
                    match = re.search(r'\s+(\d+)\s+\w{3}\s+\d+', result)
                    if match and int(match.group(1)) == expected_size:
                        if expected_md5:
                            verify_out = pyats_device.execute(f"verify /md5 {dest_path} {expected_md5}", timeout=600)
                            if "Verified" in verify_out:
                                return [("PASS", f"File {file_name} already exists and MD5 verified. Skipping transfer.")]
                except Exception:
                    pass
            
            # 2. Setup Dialog Handler for copy prompts
            dialog = Dialog([
                Statement(pattern=r'Destination filename \[.*\]\?', action='sendline()', loop_continue=True),
                Statement(pattern=r'Do you want to over write\? \[confirm\]', action='sendline()', loop_continue=True),
                Statement(pattern=r'\[confirm\]', action='sendline()', loop_continue=True),
                Statement(pattern=r'Address or name of remote host', action='sendline()', loop_continue=True),
                Statement(pattern=r'(?i)error', action=None, loop_continue=False),
                Statement(pattern=r'(?i)timed out', action=None, loop_continue=False),
            ])
            
            # 3. Transfer (Attempt exactly twice per user request)
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
                        last_err = f"Output: {result}"
                except Exception as e:
                    last_err = str(e)
                    
            try:
                pyats_device.default.log_stdout = True
            except Exception:
                pass
                
            if not success:
                return [("FAIL", f"File transfer failed after {max_attempts} attempts. Last error: {last_err}")]
                    
            # 4. Post-Check Verification
            if expected_md5:
                try:
                    verify_out = pyats_device.execute(f"verify /md5 {dest_path} {expected_md5}", timeout=600)
                    if "Verified" not in verify_out:
                        return [("FAIL", f"Post-download MD5 verification failed. Output: {verify_out}")]
                except Exception as e:
                    return [("FAIL", f"MD5 verification command failed: {str(e)}")]
            
            return [("PASS", f"Successfully distributed {file_name} to {boot_drive}")]
