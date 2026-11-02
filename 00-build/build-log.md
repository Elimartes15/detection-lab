# Build Log

Each day's folder holds a **cumulative** `log.md`: everything from day one up to and including that date. The most recent folder is always the full log. Screenshots and command output for a day sit next to its `log.md`.

**Current full log:** [2026-11-01](2026-11-01/log.md)

| Date | Focus | Highlights | Issues |
| --- | --- | --- | --- |
| [2026-10-17](2026-10-17/log.md) | Planning | Architecture, RAM sizing, OS choices | — |
| [2026-10-19](2026-10-19/log.md) | Wazuh and Proxmox | Wazuh evaluated on mini PC 1; Proxmox installed on the G5 | 1 |
| [2026-10-20](2026-10-20/log.md) | SIEM decision | Elastic Security replaces Wazuh | — |
| [2026-10-21](2026-10-21/log.md) | Network build | Disk health, `vm-lab` pool, switch trunk, OPNsense, VLANs, DHCP | 3 |
| [2026-10-22](2026-10-22/log.md) | Planning | Network diagrams, firewall policy, Kali placement | — |
| [2026-10-23](2026-10-23/log.md) | Firewall | Aliases, CLIENTS baseline started | — |
| [2026-10-24](2026-10-24/log.md) | Firewall, DC01, WS01 | CLIENTS and SERVERS rules, DC01 and WS01 built and tested | 3 |
| [2026-10-26](2026-10-26/log.md) | Domain, templates, switch, Kali | Firewall baseline complete, `cybereli.local`, Windows 11 template, WS01/WS02 joined, switch hardened, Kali installed and attacker zone verified | 7 |
| [2026-10-28](2026-10-28/log.md) | Elastic SIEM | `elastic01` VM, Elasticsearch 9.5.5, Kibana, admin port forwards | — |
| [2026-10-29](2026-10-29/log.md) | Fleet and telemetry | Fleet Server, `Fleet_Ports` rules, Sysmon + Elastic Agent on DC01/WS01/WS02, first events in Kibana | 4 |
| [2026-10-31](2026-10-31/log.md) | Audit policy | Static DHCP for WS01/WS02, domain-wide audit + PowerShell logging GPO, 4688 and 4104 verified in Kibana | 3 |
| [2026-11-01](2026-11-01/log.md) | Scenario 001 | First Sigma rule, EQL + KQL conversions, rule validated (4 alerts), Analyzer process tree, case SCN-001 | 3 |

Design choices and their reasoning live in [design decisions](../docs/design-decisions.md).
