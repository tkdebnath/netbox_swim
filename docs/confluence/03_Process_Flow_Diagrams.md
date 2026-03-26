# Process Flow Diagrams

This page contains visual diagrams for the core operational workflows in the SWIM plugin.

---

## 1. Device Sync Flow

The sync operation collects live facts from a device via SSH and compares them against NetBox records.

```mermaid
flowchart TD
    A[User triggers Sync] --> B{Single or Bulk?}
    B -->|Single| C[execute_sync_job via RQ]
    B -->|Bulk| D[execute_bulk_sync_batch via RQ]
    D --> E[ThreadPoolExecutor - max_concurrency threads]
    E --> C

    C --> F[_sync_device_logic]
    F --> G{Device has Primary IP?}
    G -->|No| H[ABORT - Create record status=aborted]
    G -->|Yes| I{Platform matches Cisco keywords?}
    I -->|No| H
    I -->|Yes| J{Credentials available?}
    J -->|No| H
    J -->|Yes| K[Select SSH library based on connection_library param]

    K -->|scrapli| L1[SyncCiscoIosDeviceScrapli]
    K -->|netmiko| L2[SyncCiscoIosDeviceNetmiko]
    K -->|unicon| L3[SyncCiscoIosDeviceUnicon]

    L1 --> M[SSH Connect + Run Commands]
    L2 --> M
    L3 --> M

    M --> N["show version → CiscoShowVersionParser"]
    N --> O["show inventory → CiscoShowInventoryParser"]
    O --> P["show running-config + show interface → CiscoShowTacacsParser"]
    P --> Q[Build golden_schema dict]

    Q --> R[_process_cisco_ios_facts]
    R --> S{Differences detected?}
    S -->|No| T["Status: no_change"]
    S -->|Yes auto_update=True| U["Apply changes → Status: auto_applied"]
    S -->|Yes auto_update=False| V["Status: pending - awaiting manual approval"]

    T --> W[Update device custom fields]
    U --> W
    V --> W
    W --> X[Finalize SyncJob status]
```

---

## 2. Upgrade Job Lifecycle

The upgrade job executes a full workflow template step by step.

```mermaid
flowchart TD
    A[User submits Upgrade Job] --> B[execute_upgrade_job via RQ]
    B --> C{Another active job on same device?}
    C -->|Yes| D[FAIL - Collision detected]
    C -->|No| E[Set status = running]

    E --> F{Last sync older than 30 min?}
    F -->|Yes| G[Force pre-flight sync]
    G --> H{Sync successful?}
    H -->|No| I[FAIL - Pre-flight sync failed]
    H -->|Yes| J[Continue]
    F -->|No| J

    J --> K[Load WorkflowTemplate steps ordered by step.order]
    K --> L{Next step?}
    L -->|Done| M[Generate checks archive ZIP]

    L --> N{Step type?}
    N -->|ping| O[ICMP/TCP:22 with retries]
    N -->|wait| P["Sleep for extra_config.duration seconds"]
    N -->|report| Q[Generate summary from all JobLogs]
    N -->|SSH step| R[Resolve connection priority]

    O --> S{Step passed?}
    P --> S
    Q --> S
    R --> T[Try each library in priority order]

    T --> U{Library available?}
    U -->|No| V[Skip to next library]
    V --> U
    U -->|Yes| W[executor.execute via SSH]
    W --> X{Result type?}

    X -->|"list of tuples"| Y[Check for failures/stubs]
    X -->|"tuple bool,str"| Z[Check success flag]
    X -->|other| AA[Log raw output]

    Y --> S
    Z --> S
    AA --> S

    S -->|Pass| L
    S -->|Fail on verification/postcheck/report| AB[Log warning but continue pipeline]
    S -->|Fail on other steps| AC[HALT pipeline]

    AB --> L
    AC --> M

    M --> AD[Write job_log.txt into archive]
    AD --> AE["Create ZIP: devicename_checks_ddmmyy.zip"]
    AE --> AF[Set final job status]
    AF --> AG{Any failures?}
    AG -->|No| AH[Status: completed]
    AG -->|Yes| AI[Status: failed]
```

---

## 3. Connection Library Fallback

Each SSH-requiring step tries connection libraries in priority order:

```mermaid
flowchart LR
    A[Step requires SSH] --> B[Read connection_priority]
    B --> C["Priority list e.g. scrapli,netmiko,unicon"]
    C --> D{Try library 1}
    D -->|Success| E[Step PASS - break]
    D -->|Stub detected| F{Try library 2}
    F -->|Success| E
    F -->|Stub detected| G{Try library 3}
    G -->|Success| E
    G -->|Fail| H[Step FAIL - all libraries exhausted]
```

**Priority Resolution Order:**
1. `extra_config.connection_library` on the WorkflowStep (highest)
2. `extra_config.connection_priority_override` on the UpgradeJob
3. `HardwareGroup.connection_priority` field
4. Default: `scrapli,netmiko,unicon`

---

## 4. File Server Resolution

When the engine needs to locate a firmware image for a device:

```mermaid
flowchart TD
    A[Engine needs image file for Device X] --> B[Query FileServer table]
    B --> C{Device in fs.devices M2M?}
    C -->|Yes| D["Tier 1: Device-specific match"]
    C -->|No| E{Device.site in fs.sites?}
    E -->|Yes| F["Tier 2: Site match"]
    E -->|No| G{Device.site.region in fs.regions?}
    G -->|Yes| H["Tier 3: Region match"]
    G -->|No| I{fs.is_global_default = True?}
    I -->|Yes| J["Tier 4: Global default"]
    I -->|No| K[No file server found]

    D --> L[Sort by priority ascending]
    F --> L
    H --> L
    J --> L
    L --> M[Return ordered list - best match first]
```

---

## 5. Compliance Evaluation

```mermaid
flowchart TD
    A[Compliance check triggered] --> B[For each device with a sync record]
    B --> C[Get device.custom_field_data.software_version]
    C --> D[Find matching HardwareGroup]
    D --> E[Look up GoldenImage for that group + deployment_mode]
    E --> F{Golden image found?}
    F -->|No| G["Status: unknown"]
    F -->|Yes| H{Running version == Golden version?}
    H -->|Yes| I["Status: compliant"]
    H -->|No| J{Running version newer than Golden?}
    J -->|Yes| K["Status: ahead"]
    J -->|No| L["Status: non_compliant"]
```

---

## 6. Bulk Sync Architecture

```mermaid
flowchart TD
    A["User selects N devices + clicks Sync"] --> B[POST to bulk_sync endpoint]
    B --> C["RQ enqueues execute_bulk_sync_batch"]
    C --> D["Create SyncJob record"]
    D --> E["ThreadPoolExecutor with max_concurrency workers"]
    E --> F1["Thread 1: _sync_device_logic Device A"]
    E --> F2["Thread 2: _sync_device_logic Device B"]
    E --> F3["Thread N: _sync_device_logic Device N"]

    F1 --> G["SSH → Parse → Diff → Save DeviceSyncRecord"]
    F2 --> G
    F3 --> G

    G --> H["All threads complete"]
    H --> I["Count failures + aborts"]
    I --> J{Any failures?}
    J -->|None| K["SyncJob.status = completed"]
    J -->|Some| L["SyncJob.status = failed"]
    J -->|All aborted| M["SyncJob.status = aborted"]
```

---

## 7. Checks Archive ZIP Structure

After an upgrade job completes, a diagnostic archive is generated:

```
C9K-SWI01_checks_260326.zip
├── precheck/
│   ├── bgp_summary.txt
│   ├── ospf_neighbors.txt
│   ├── interface_status.txt
│   └── ...
├── postcheck/
│   ├── bgp_summary.txt
│   ├── ospf_neighbors.txt
│   ├── interface_status.txt
│   └── ...
├── diffs/
│   ├── diff_bgp_summary.txt
│   ├── diff_ospf_neighbors.txt
│   └── summary.log
└── job_log.txt
```

The `diffs/` folder is generated either by:
- **Genie diff CLI** (preferred — structured parsing)
- **Python difflib** (fallback — text-based unified diff)
