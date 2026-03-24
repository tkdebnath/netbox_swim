"""
Global Constants and Configuration for the SWIM Plugin
"""

# Master mapping translating generic NetBox OS strings into library-specific dialects.
# This serves as the single source of truth for all Scrapli, Netmiko, Unicon, TextFSM, and Genie instances globally.
PLATFORM_MAPPINGS = {
    'cisco-ios': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'ios',
        'textfsm': 'cisco_ios',
        'genie': 'ios'
    },
    'ios': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'ios',
        'textfsm': 'cisco_ios',
        'genie': 'ios'
    },
    'cisco-ios-xe': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'iosxe',
        'textfsm': 'cisco_ios',
        'genie': 'iosxe'
    },
    'cisco_iosxe': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'iosxe',
        'textfsm': 'cisco_ios',
        'genie': 'iosxe'
    },
    'iosxe': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'iosxe',
        'textfsm': 'cisco_ios',
        'genie': 'iosxe'
    },
    
    'cisco-nx-os': {
        'scrapli': 'cisco_nxos',
        'netmiko': 'cisco_nxos',
        'unicon': 'nxos',
        'textfsm': 'cisco_nxos',
        'genie': 'nxos'
    },
    'cisco_nxos': {
        'scrapli': 'cisco_nxos',
        'netmiko': 'cisco_nxos',
        'unicon': 'nxos',
        'textfsm': 'cisco_nxos',
        'genie': 'nxos'
    },
    'nxos': {
        'scrapli': 'cisco_nxos',
        'netmiko': 'cisco_nxos',
        'unicon': 'nxos',
        'textfsm': 'cisco_nxos',
        'genie': 'nxos'
    },
    
    'juniper-junos': {
        'scrapli': 'juniper_junos',
        'netmiko': 'juniper_junos',
        'unicon': 'junos',
        'textfsm': 'juniper_junos',
        'genie': 'junos'
    },
    'junos': {
        'scrapli': 'juniper_junos',
        'netmiko': 'juniper_junos',
        'unicon': 'junos',
        'textfsm': 'juniper_junos',
        'genie': 'junos'
    },
    
    'arista-eos': {
        'scrapli': 'arista_eos',
        'netmiko': 'arista_eos',
        'unicon': 'eos',
        'textfsm': 'arista_eos',
        'genie': 'eos'
    },
    'eos': {
        'scrapli': 'arista_eos',
        'netmiko': 'arista_eos',
        'unicon': 'eos',
        'textfsm': 'arista_eos',
        'genie': 'eos'
    },
    
    'paloalto-panos': {
        'scrapli': 'paloalto_panos',
        'netmiko': 'paloalto_panos',
        'unicon': 'panos',
        'textfsm': 'paloalto_panos',
        'genie': 'panos'
    },
    'panos': {
        'scrapli': 'paloalto_panos',
        'netmiko': 'paloalto_panos',
        'unicon': 'panos',
        'textfsm': 'paloalto_panos',
        'genie': 'panos'
    },
    
    # Generic universal fallback
    'default': {
        'scrapli': 'cisco_iosxe',
        'netmiko': 'cisco_ios',
        'unicon': 'iosxe',
        'textfsm': 'cisco_ios',
        'genie': 'iosxe'
    }
}

# ============================================================
# Custom Field Registry
# ============================================================
# Simply append or remove dictionary items to this list, and they will 
# reload upon container restart.
SWIM_CUSTOM_FIELDS = [
    {
        'name': 'deployment_mode',
        'type': 'select',
        'label': 'Deployment Mode',
        'description': 'Network deployment context for SWIM compliance (Campus vs. SD-WAN)',
        'weight': 100,
        'choices': [
            ['campus', 'Campus / Traditional'],
            ['sdwan', 'SD-WAN'],
            ['universal', 'Universal (Both)'],
        ]
    },
    {
        'name': 'software_version',
        'type': 'text',
        'label': 'Current Software Version',
        'description': 'Currently running software/firmware version (e.g., 17.9.4)',
        'weight': 110,
    },
    {
        'name': 'tacacs_source_interface',
        'type': 'text',
        'label': 'TACACS Source Interface',
        'description': 'Discovered TACACS+ source-interface',
        'weight': 120,
    },
    {
        'name': 'tacacs_source_ip',
        'type': 'text',
        'label': 'TACACS Source IP',
        'description': 'Discovered TACACS+ source IP address',
        'weight': 130,
    },
    {
        'name': 'vrf',
        'type': 'text',
        'label': 'VRF',
        'description': 'Discovered VRF routing instance',
        'weight': 140,
    },
    {
        'name': 'swim_last_sync_status',
        'type': 'select',
        'label': 'Last Sync Status',
        'description': 'Execution result of the last sync attempt.',
        'weight': 150,
        'choices': [
            ['success', 'Success'],
            ['error', 'Error'],
            ['pending', 'Pending']
        ]
    },
    {
        'name': 'swim_last_successful_sync',
        'type': 'datetime',
        'label': 'Last Successful Sync',
        'description': 'Timestamp of the last fully successful sync execution.',
        'weight': 160,
    }
]
