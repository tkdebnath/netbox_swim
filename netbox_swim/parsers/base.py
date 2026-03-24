class BaseCommandParser:
    """
    Base class for CLI output parsers.
    Subclasses return a standardized dictionary ("golden schema")
    regardless of vendor or parse engine used.
    """
    def __init__(self, raw_string, platform_slug=''):
        self.raw_string = raw_string
        self.platform_slug = platform_slug.lower()
        
        from netbox_swim.constants import PLATFORM_MAPPINGS
        
        # Look up TextFSM and Genie platform strings from the slug
        dialect = PLATFORM_MAPPINGS.get(self.platform_slug, PLATFORM_MAPPINGS['default'])
        
        self.textfsm_platform = dialect['textfsm']
        self.genie_platform = dialect['genie']
        
        self.structured_facts = self._initialize_schema()

    def _initialize_schema(self):
        """
        Returns the default Golden Schema dictionary for this specific command.
        Must be implemented by subclasses (e.g., {'hostname': None, 'serial': None})
        """
        raise NotImplementedError("Subclasses must define their schema.")

    def get_facts(self):
        """
        Executes the cross-referencing parsing engines (TextFSM + Genie) 
        and returns the fully populated, validated schema.
        """
        raise NotImplementedError("Subclasses must implement data merge logic.")

    def _parse_with_textfsm(self, command, raw_string_override=None):
        """Parse raw CLI output using NTC TextFSM templates. Returns list of dicts."""
        try:
            from ntc_templates.parse import parse_output
            # If a complex multi-stage parser injects a specific string, use it. Otherwise use the default self.raw_string
            data_to_parse = raw_string_override if raw_string_override is not None else self.raw_string
            parsed_list = parse_output(platform=self.textfsm_platform, command=command, data=data_to_parse)
            return parsed_list if parsed_list else []
        except Exception:
            # NTC template missing or parse error; fall through to Genie
            return [] 

    def _parse_with_genie(self, command, raw_string_override=None):
        """Parse raw CLI output using Genie parsers. Returns nested dict."""
        try:
            from genie.conf.base import Device
            data_to_parse = raw_string_override if raw_string_override is not None else self.raw_string
            mock_device = Device(name='mock_device', os=self.genie_platform)
            mock_device.custom.abstraction = {'order': ['os']}
            return mock_device.parse(command, output=data_to_parse)
        except Exception:
            # Genie parse error; return empty so caller falls through
            return {}
