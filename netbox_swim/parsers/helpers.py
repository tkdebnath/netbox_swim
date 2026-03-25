import re

def get_ios_management_context(running_config: str, interface_output: str, ip_address: str) -> dict:
    """
    Scans the running config block to locate the configured TACACS source interface.
    If found, it returns that interface, its IP, and its VRF.
    If NOT found, it falls back to finding which Interface possesses the specified IP address (the management connection IP).
    """
    context = {
        'interface': None,
        'ip_address': ip_address,
        'vrf': ''
    }
    
    if not running_config:
        return context

    # 1. Look for explicit TACACS source interface configuration
    tacacs_match = re.search(r'(?:ip tacacs|tacacs-server)\s+source-interface\s+([A-Za-z0-9/.-]+)', running_config, re.IGNORECASE)
    target_interface = tacacs_match.group(1) if tacacs_match else None

    # 2. Split config into individual interface blocks
    blocks = running_config.split("\ninterface ")
    
    # Initialize tracking variables outside loop
    found_target_match = False

    for block in blocks:
        if not block.strip():
            continue
            
        lines = block.splitlines()
        intf_name = lines[0].strip()
        
        # Check if interface is administratively down
        is_shutdown = any(line.strip().lower() == 'shutdown' for line in lines)
        
        # We need to find the IP and VRF of either the explicit TACACS target, or the fallback IP
        ip_found = False
        vrf_name = ''
        block_ip = ''
        
        for line in lines[1:]:
            line_str = line.strip().lower()
            if line_str.startswith('ip address '):
                # E.g. "ip address 10.0.0.1 255.255.255.0"
                parts = line_str.split()
                if len(parts) >= 3:
                    block_ip = parts[2]
                if ip_address and ip_address in line_str:
                    ip_found = True
            elif line_str.startswith('vrf forwarding '):
                vrf_name = line.strip().split('vrf forwarding ')[-1].strip()
            elif line_str.startswith('ip vrf forward '):
                vrf_name = line.strip().split('ip vrf forward ')[-1].strip()
                
        # Condition A: We found the explicitly configured TACACS source interface
        if target_interface and intf_name.lower() == str(target_interface).lower():
            if is_shutdown:
                continue # Skip shutdown interfaces
                
            found_target_match = True
            context['interface'] = intf_name
            context['vrf'] = vrf_name
            if block_ip:
                context['ip_address'] = block_ip
                return context # Fully resolved!
            # If there's no IP in the config block, we do NOT return yet. Let it fall through to 'show interface' parsing
            break
            
        # Condition B: No explicit TACACS config, but this interface has the fallback IP we used to connect
        if not target_interface and ip_found:
            if is_shutdown:
                continue
            context['interface'] = intf_name
            context['vrf'] = vrf_name
            return context
            
    # Condition C: TACACS source interface is configured but IP address is not found in running config.
    # We fallback to looking in the 'show interface' output if the IP wasn't in the running config
    if interface_output and target_interface and found_target_match:
        context['interface'] = target_interface
        # Naive IP extraction from show interface block
        match = re.search(rf'{target_interface}.*?Internet address is ([0-9.]+)', interface_output, re.IGNORECASE | re.DOTALL)
        if match:
            context['ip_address'] = match.group(1)

    return context
