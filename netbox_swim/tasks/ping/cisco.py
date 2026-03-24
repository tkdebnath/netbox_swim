import subprocess

class PingReachabilityStep:
    """
    Continually pings the device until it successfully responds or the timeout breaks.
    """
    def execute(self, device, timeout_seconds=600):
        logs = []
        host = getattr(device, 'primary_ip', None)
        if not host:
            return [("failed", "Ping failed: No primary IP defined on device object.")]
        
        ip = str(host).split('/')[0]
        logs.append(("info", f"Initiating ICMP Reachability Checks against {ip} for up to {timeout_seconds} seconds..."))
        
        # Windows ping uses "-n", Linux/MacOS use "-c"
        import platform
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        
        import time
        start = time.time()
        while time.time() - start < timeout_seconds:
            command = ['ping', param, '1', ip]
            # Use subprocess to hide ping output
            response = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if response == 0:
                 logs.append(("success", f"Host {ip} responded to ICMP! Re-established connectivity at {int(time.time()-start)}s."))
                 logs.append(("pass", "Ping reachability step certified."))
                 return logs
                 
            time.sleep(10)
            
        logs.append(("failed", f"Host {ip} never returned a ping within {timeout_seconds}s limit! Possible boot failure."))
        return logs
