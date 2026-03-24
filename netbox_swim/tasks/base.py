from contextlib import contextmanager

class UpgradeTask:
    """Base atomic task for any upgrade action."""
    def execute(self, device, target_image):
        """
        Execute the task. 
        Must return a list of tuples: [('pass', 'Message'), ('fail', 'Error')]
        """
        raise NotImplementedError

    def _get_credentials(self, device):
        """
        Extracts credentials cleanly from NetBox config contexts or OS environments,
        abstracting this logic away from specific connection libraries.
        Returns: host, username, password, secret, platform_slug
        """
        import os
        config_context = device.get_config_context()
        swim_config = config_context.get('swim', {})
        cred_profile = swim_config.get('credential_profile')
        
        if cred_profile:
            # If NetBox dictates a specific profile, we pull that key from the OS
            username = os.environ.get(f"{cred_profile.upper()}_USERNAME", "")
            password = os.environ.get(f"{cred_profile.upper()}_PASSWORD", "")
            secret = os.environ.get(f"{cred_profile.upper()}_SECRET", "")
        else:
            # Fallback to general environment variables if no profile is defined
            username = os.environ.get('SWIM_USERNAME', '')
            password = os.environ.get('SWIM_PASSWORD', '')
            secret = os.environ.get('SWIM_SECRET', '')
            
        # We no longer fall back to device.name. 
        host = str(device.primary_ip.address.ip) if device.primary_ip else ''
        platform_slug = getattr(device.platform, 'slug', '')
        
        return host, username, password, secret, platform_slug

    def _get_boot_drive(self, device, target_image=None):
        """
        Resolves the file system prefix (e.g. 'flash:' vs 'bootflash:')
        1. Checks Config Context for overrides
        2. Checks the assigned HardwareGroup extra_config
        3. Falls back to model string heuristics
        """
        # Config Context override (highest precedence)
        ctx = device.get_config_context()
        if 'swim_boot_drive' in ctx:
            return ctx['swim_boot_drive']

        # 2. Hardware Group Override
        if target_image:
            hw_group = getattr(target_image, 'hardware_groups', None)
            if hw_group and hw_group.exists():
                grp = hw_group.first()
                if isinstance(grp.extra_config, dict) and 'swim_boot_drive' in grp.extra_config:
                    return grp.extra_config['swim_boot_drive']

        # 3. Regex fallback based on OS + Model hardware
        model = getattr(getattr(device, 'device_type', None), 'model', '').upper()
        platform_slug = getattr(getattr(device, 'platform', None), 'slug', '').lower()
        
        if 'nxos' in platform_slug or 'nx-os' in platform_slug:
            # Nexus always defaults to bootflash:
            return "bootflash:"
            
        if 'ios-xe' in platform_slug or 'ios' in platform_slug:
            # Only exact modern IOS-XE chassis like Cat9k / ASR / CSR default to bootflash:
            if any(x in model for x in ['9500', '9600', '9400', 'ASR', 'CSR']):
                return "bootflash:"
            return "flash:"
            
        # Generic Default
        return "flash:"

class ScrapliTask(UpgradeTask):
    """Adapter for raw Scrapli connections."""
    @contextmanager
    def connect(self, device, **kwargs):
        from scrapli import Scrapli
        
        from ..constants import PLATFORM_MAPPINGS
        
        # 1. Ask the parent class for the standardized variables
        host, username, password, secret, platform_slug = self._get_credentials(device)
        
        # 2. Tap the Global Mapper to retrieve Scrapli's specifically required dialect
        dialect = PLATFORM_MAPPINGS.get(platform_slug, PLATFORM_MAPPINGS['default'])
        
        # 3. Construct the Scrapli-specific connection dictionary
        conn_dict = {
            "host": host,
            "auth_username": username,
            "auth_password": password,
            "auth_strict_key": False,
            "transport": "system",
            "platform": dialect['scrapli'],
            "timeout_socket": 15,
            "timeout_transport": 30,
            "timeout_ops": 30,
            "transport_options": {
                "open_cmd": [
                    "-o", "ConnectTimeout=15",
                    "-o", "ServerAliveInterval=10",
                    "-o", "ServerAliveCountMax=3",
                    "-o", "KexAlgorithms=+diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1,diffie-hellman-group1-sha1",
                    "-o", "HostKeyAlgorithms=+ssh-rsa",
                    "-o", "Ciphers=+aes256-cbc"
                ]
            }
        }
        
        # Only inject the secret if one was actually provided
        if secret:
            conn_dict["auth_secondary"] = secret
            
        # Support **kwargs injections globally
        conn_dict.update(kwargs)
        
        conn = Scrapli(**conn_dict)
        conn.open()
        try:
            yield conn
        finally:
            conn.close()

class NetmikoTask(UpgradeTask):
    """Adapter for standard Netmiko connections."""
    @contextmanager
    def connect(self, device, **kwargs):
        from netmiko import ConnectHandler
        
        from ..constants import PLATFORM_MAPPINGS
        
        host, username, password, secret, platform_slug = self._get_credentials(device)
        
        dialect = PLATFORM_MAPPINGS.get(platform_slug, PLATFORM_MAPPINGS['default'])
        
        device_dict = {
            'device_type': dialect['netmiko'],
            'host': host,
            'username': username,
            'password': password,
            'fast_cli': False,
            'conn_timeout': 60,
            'session_timeout': 60,
            'global_delay_factor': 1
        }
        
        if secret:
            device_dict['secret'] = secret
            
        device_dict.update(kwargs)
        
        with ConnectHandler(**device_dict) as conn:
            if secret:
                try:
                    conn.enable()
                except Exception:
                    pass
            yield conn

class UniconTask(UpgradeTask):
    """Adapter for Unicon automation scripts."""
    @contextmanager
    def connect(self, device, **kwargs):
        from genie.testbed import load
        
        from ..constants import PLATFORM_MAPPINGS
        
        host, username, password, secret, platform_slug = self._get_credentials(device)
        dialect = PLATFORM_MAPPINGS.get(platform_slug, PLATFORM_MAPPINGS['default'])
        
        # Construct credentials
        creds = {
            'default': {
                'username': username,
                'password': password
            }
        }
        if secret:
            creds['enable'] = {'password': secret}
            
        # Build the pyATS testbed config dict
        tb_conf = {
            'devices': {
                str(device.name): {
                    'os': dialect['unicon'],
                    'credentials': creds,
                    'connections': {
                        'cli': {
                            'protocol': 'ssh',
                            'ip': host,
                            'ssh_options': '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                        }
                    }
                }
            }
        }
        
        tb = load(tb_conf)
        pyats_device = tb.devices[str(device.name)]
        
        # Suppress logging spam
        import logging
        logging.getLogger('unicon').setLevel(logging.CRITICAL)
        
        pyats_device.connect(alias='cli', log_stdout=False, **kwargs)
        
        try:
            yield pyats_device
        finally:
            pyats_device.disconnect()

class PanosRestTask(UpgradeTask):
    """Adapter for Palo Alto REST connections."""
    def connect(self, device):
        # Boilerplate for PAN-OS XML/REST API
        pass

    def execute(self, device, target_image):
        """Implement to use self.connect()"""
        raise NotImplementedError
