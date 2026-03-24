# Workflows & Validation

SWIM uses workflow templates to define the step-by-step sequence that runs during a firmware upgrade. Validation checks and check templates let you define pre/post health tests.

## 1. Validation Checks
Individual test rules that run a command on a device and evaluate the output.
- **Platform**: Which platform this check applies to (e.g. `cisco_ios`).
- **Command**: The CLI command to run, e.g. `show file systems`.
- **JSON Path / Operator / Expected Value**: How to evaluate the parsed output. E.g. `.flash.freespace` `<` `5000000`.

### Validation Checks API Operations
- **Endpoint:** `/api/plugins/swim/validation-checks/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

```python
import requests
payload = {
    "name": "Verify Adequate BGP Neighbors",
    "platform": "cisco_ios",
    "command": "show ip bgp summary",
    "operator": ">=",
    "expected_value": "3",
}
requests.post("http://<netbox>/api/plugins/swim/validation-checks/", json=payload, headers=HEADERS)
```

---

## 2. Check Templates
A Check Template groups multiple `ValidationCheck` records into a suite (e.g. "Pre-Flight Checks", "Core Routing Tests").

### Check Template API Operations
- **Endpoint:** `/api/plugins/swim/check-templates/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

```python
# Create a template that bundles three individual checks
requests.post("http://<netbox>/api/plugins/swim/check-templates/", headers=HEADERS, json={
    "name": "Global Pre-Execution Tests Suite",
    "checks": [1, 5, 8]  # ValidationCheck PKs
})
```

---

## 3. Workflow Templates & Steps
A `WorkflowTemplate` defines the ordered pipeline of actions that execute during an upgrade. A `WorkflowStep` represents a single action within that pipeline (`precheck`, `distribution`, `activation`, `wait`, `ping`, etc.).

For `wait` and `ping` steps, use the `extra_config` JSON field to set parameters.

### Workflows API Operations
- **Endpoints:** `/api/plugins/swim/workflow-templates/` AND `/api/plugins/swim/workflow-steps/`
- **Methods:** `GET`, `POST`, `PATCH`, `DELETE`

**Creating a workflow with steps:**
```python
# 1. Create the template
tmpl_res = requests.post("http://<netbox>/api/plugins/swim/workflow-templates/", headers=HEADERS, json={
    "name": "Safe Reload OS Upgrade Template",
    "is_active": True
})
tmpl_pk = tmpl_res.json()['id']

# 2. Add a pre-check step
requests.post("http://<netbox>/api/plugins/swim/workflow-steps/", headers=HEADERS, json={
    "template": tmpl_pk,
    "order": 10,
    "action_type": "precheck",
    "extra_config": {}  # Check Templates are assigned separately via the UI or API
})

# 3. Add a wait step (pause pipeline for 300 seconds)
requests.post("http://<netbox>/api/plugins/swim/workflow-steps/", headers=HEADERS, json={
    "template": tmpl_pk,
    "order": 20,
    "action_type": "wait",
    "extra_config": {"delay_seconds": 300}
})

# 4. Add a ping step (verify device is reachable after reload)
requests.post("http://<netbox>/api/plugins/swim/workflow-steps/", headers=HEADERS, json={
    "template": tmpl_pk,
    "order": 30,
    "action_type": "ping",
    "extra_config": {"count": 5, "interval": 10, "timeout": 120}
})
```

### Extra Config Reference

| Action Type | Field              | Description                          |
|-------------|--------------------|--------------------------------------|
| `wait`      | `delay_seconds`    | Number of seconds to pause           |
| `ping`      | `target_ip`        | IP to ping (defaults to primary IP)  |
| `ping`      | `count`            | Number of ping attempts              |
| `ping`      | `interval`         | Seconds between pings                |
| `ping`      | `timeout`          | Max seconds to wait for response     |
