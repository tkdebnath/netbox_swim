import time

class WaitLifecycleStep:
    """
    Standard wait timer step to allow device OS loading intervals to progress neutrally.
    """
    def execute(self, device, duration_seconds=300):
        logs = []
        logs.append(("info", f"Initiating forced sleep interval for {duration_seconds} seconds..."))
        time.sleep(duration_seconds)
        logs.append(("pass", f"Wait timer completed ({duration_seconds}s)."))
        return logs
