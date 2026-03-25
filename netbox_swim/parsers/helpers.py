import re

def get_ios_management_context(running_config: str, interface_output: str, ip_address: str) -> dict:
    """
    Evaluates TACACS source-interface logic:
    1. Checks if global tacacs source-interface exists.
    2. If it does, checks if it is not shutdown.
    3. Records VRF and IP (if static).
    4. If DHCP, polls 'show interface' output for dynamic IP.
    5. If anything fails (shutdown, no IP found), falls back to finding the interface that owns the connection IP.
    """
    context = {
        'interface': None,
        'ip_address': ip_address,
        'vrf': ''
    }
    
    if not running_config:
        return context

    # --- Pre-parse 'show interface' to map dynamically assigned IPs cleanly ---
    show_intf_ips = {}
    if interface_output:
        current_intf = None
        for line in interface_output.splitlines():
            if line and not line[0].isspace():
                # E.g. "Vlan100 is up, line protocol is up"
                current_intf = line.split(" is ")[0].strip().lower()
            elif current_intf and 'Internet address is ' in line:
                match = re.search(r'Internet address is ([0-9.]+)', line)
                if match:
                    show_intf_ips[current_intf] = match.group(1)

    # --- Pre-parse 'show running-config' into interface dictionaries ---
    parsed_ints = {}
    fallback_intf = None
    
    blocks = running_config.split("\ninterface ")
    for block in blocks:
        if not block.strip():
            continue
            
        lines = block.splitlines()
        intf_name = lines[0].strip()
        intf_key = intf_name.lower()
        
        is_shutdown = any(line.strip().lower() == 'shutdown' for line in lines)
        is_dhcp = any('ip address dhcp' in line.strip().lower() for line in lines)
        block_ip = ''
        vrf_name = ''
        has_fallback = False
        
        for line in lines[1:]:
            line_str = line.strip().lower()
            if line_str.startswith('ip address ') and 'dhcp' not in line_str:
                parts = line_str.split()
                if len(parts) >= 3:
                    block_ip = parts[2]
                if ip_address and ip_address in line_str:
                    has_fallback = True
            elif line_str.startswith('vrf forwarding '):
                vrf_name = line.strip().split('vrf forwarding ')[-1].strip()
            elif line_str.startswith('ip vrf forward '):
                vrf_name = line.strip().split('ip vrf forward ')[-1].strip()
                
        parsed_data = {
            'name': intf_name,
            'shutdown': is_shutdown,
            'ip': block_ip,
            'dhcp': is_dhcp,
            'vrf': vrf_name,
            'has_fallback': has_fallback
        }
        parsed_ints[intf_key] = parsed_data
        
        if has_fallback:
            fallback_intf = parsed_data

    # --- 1. Evaluate Global TACACS configuration ---
    tacacs_match = re.search(r'(?:ip tacacs|tacacs-server)\s+source-interface\s+([A-Za-z0-9/.-]+)', running_config, re.IGNORECASE)
    target_intf = tacacs_match.group(1).lower() if tacacs_match else None

    if target_intf and target_intf in parsed_ints:
        t_data = parsed_ints[target_intf]
        
        if not t_data['shutdown']:
            target_ip = t_data['ip']
            if not target_ip and t_data['dhcp']:
                target_ip = show_intf_ips.get(target_intf)
            
            if target_ip:
                context['interface'] = str(t_data['name'])
                context['ip_address'] = str(target_ip)
                context['vrf'] = str(t_data['vrf'])
                return context

    # --- 2. Fallback execution if global target failed or missing ---
    # Find the interface matching the connection 'fallback' IP explicitly
    if fallback_intf and not fallback_intf['shutdown']:
        context['interface'] = str(fallback_intf['name'])
        context['ip_address'] = str(fallback_intf['ip'] or ip_address)
        context['vrf'] = str(fallback_intf['vrf'])
        return context

    # --- 3. Final Fallback (If fallback connection IP was assigned purely via DHCP) ---
    if ip_address:
        for intf_key, intf_data in parsed_ints.items():
            if intf_data['dhcp'] and not intf_data['shutdown']:
                if show_intf_ips.get(intf_key) == ip_address:
                    context['interface'] = str(intf_data['name'])
                    context['vrf'] = str(intf_data['vrf'])
                    return context

    return context
