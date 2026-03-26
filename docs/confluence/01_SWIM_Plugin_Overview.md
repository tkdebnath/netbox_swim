# SWIM Plugin for NetBox — Project Overview

| **Field** | **Value** |
|---|---|
| **Plugin Name** | NetBox SWIM (Software Image Management) |
| **Version** | 1.0.0 |
| **Platform** | NetBox 4.x Plugin |
| **Repository** | `github.com/tkdebnath/netbox_swim` |
| **Author** | Network Engineering Team |
| **Last Updated** | March 2026 |

---

## What is SWIM?

SWIM (Software Image Management) is a NetBox plugin that automates the full lifecycle of network device firmware management — from inventory and compliance tracking to automated rolling upgrades with pre/post checks and diagnostic archives.

---

## Five Pillars

| # | Pillar | Description |
|---|--------|-------------|
| 1 | **Image Repository** | Central catalog of all firmware images, file servers, and download locations |
| 2 | **Compliance Engine** | Golden image baselines per hardware group; real-time compliant vs. non-compliant status |
| 3 | **Workflow Engine** | Customizable upgrade templates with ordered steps (readiness → precheck → distribute → activate → verify → report) |
| 4 | **Execution Engine** | Background workers (django-rq) executing SSH tasks via Scrapli, Netmiko, or Unicon with automatic library fallback |
| 5 | **Network Sync & Drift** | Live device fact collection comparing NetBox records against actual device state |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Core Platform | NetBox 4.x (Django) |
| Background Jobs | django-rq + Redis |
| SSH Libraries | Scrapli, Netmiko, Unicon (pyATS) |
| Parsing | TextFSM, Genie (pyATS) |
| Diffing | Genie diff CLI, Python difflib fallback |
| API | Django REST Framework (NetBox plugin API) |
| Testbed Generation | pyATS YAML testbed format |

---

## Navigation Menu Structure

```
OS & Firmware Upgrades
├── Overview
│   └── Dashboard
├── Image Repository
│   ├── Software Images
│   └── File Servers
├── Compliance & Workflows
│   ├── Hardware Groups
│   ├── Golden Images
│   ├── Compliance Records
│   ├── Compliance Dashboard
│   ├── Workflow Templates
│   ├── Check Templates
│   └── Validation Checks
└── Execution Engine
    ├── Upgrade Jobs
    ├── Job Logs
    ├── Consolidated Sync Results
    ├── Sync Jobs Tracking
    ├── Bulk Device Sync
    ├── Bulk Auto-Remediation
    └── pyATS Testbed Generator
```

---

## Quick Links (Internal Confluence)

| Page | Description |
|------|-------------|
| [Data Model Reference](02_Data_Model_Reference.md) | All models, fields, and relationships |
| [Process Flow Diagrams](03_Process_Flow_Diagrams.md) | Visual workflows for sync and upgrade operations |
| [User Guide](04_User_Guide.md) | Step-by-step how-to for all operations |
| [API & CLI Reference](05_API_CLI_Reference.md) | REST API endpoints and CLI automation scripts |
| [Developer & Maintenance Guide](06_Developer_Maintenance_Guide.md) | Code structure, adding new platforms, and troubleshooting |
