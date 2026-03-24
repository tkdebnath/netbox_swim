import re

def get_ios_management_context(running_config: str, ip_address: str) -> dict:
    """
    Scans the running config block to locate exactly which Interface 
    possesses the specified IP address, and grabs its associated VRF.
    """
    context = {
        'interface': None,
        'ip_address': ip_address,
        'vrf': ''
    }
    
    if not running_config or not ip_address:
        return context

    # 1. Split config into individual interface blocks
    # Looking for:
    # interface GigabitEthernet0/0/0
    #  vrf forwarding MGMT
    #  ip address 10.0.0.1 255.255.255.0
    # ...
    # !
    blocks = running_config.split("\ninterface ")
    
    for block in blocks:
        # Ignore the first chunk (global config before the first interface)
        if not block.strip() or "ip address " not in block.lower():
            continue
            
        # The first line of the block is the interface name
        lines = block.splitlines()
        intf_name = lines[0].strip()
        
        # Determine if this block contains our IP
        ip_found = False
        vrf_name = ''
        
        for line in lines[1:]:
            line_str = line.strip().lower()
            if line_str.startswith('ip address ') and ip_address in line_str:
                ip_found = True
            elif line_str.startswith('vrf forwarding '):
                # e.g., "vrf forwarding MGMT" -> "MGMT"
                vrf_name = line.strip().split('vrf forwarding ')[-1].strip()
            elif line_str.startswith('ip vrf forward '):
                # Older IOS syntax
                vrf_name = line.strip().split('ip vrf forward ')[-1].strip()
                
        if ip_found:
            context['interface'] = intf_name
            context['vrf'] = vrf_name
            break
            
    return context
