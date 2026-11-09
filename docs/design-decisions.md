# Design Decisions

Each decision records what was chosen, the alternatives, and why. Newest first.

---

## DD-030 · Rules reach Kibana only through the pipeline

- **Decision:** `kibana-deploy` upserts every Sigma rule into Kibana from `main`, keyed by the Sigma `id`. Branches only run a dry-run plan. No rule is created or edited by hand in Kibana.
- **Identity:** a dedicated `ci-deployer` user with role `ci-rule-deployer` (Rules and Exceptions, read on the source indices, own API keys), never `elastic`. Its API key is a masked, protected GitLab variable, so only `main` pipelines can deploy.
- **Why:** Git becomes the single source of truth; every live rule traces to a reviewed commit; a broken rule can't reach the SIEM without passing lint; a branch can't deploy because it can't read the key.
- **Consequences accepted:** edits made in Kibana are overwritten on the next deploy (stated in each rule's investigation guide). Changing the role requires a new API key, since keys snapshot their owner's privileges.
- **Rejected:** Elastic's `detection-rules` CLI (heavier, its own rule format); importing NDJSON exports (no per-rule upsert, harder to review).

## DD-029 · Pinned toolchain per CI job

- **Decision:** lint and conversion use separate, pinned toolchains on `ctl01`. Lint: sigma-cli 4.0 (pySigma 2.x, current ATT&CK data). Conversion: a venv pinned to sigma-cli 3.1.0, pySigma 1.5.1, `pysigma-backend-elasticsearch` 2.1.1, `pysigma-backend-kusto` 1.0.1.
- **Why:** the backends don't support pySigma 2.x yet. Forcing them in risks a conversion that runs cleanly but emits a subtly wrong query, the worst failure for a detection pipeline. Pinning means a dependency update can never silently change deployed queries.
- **Rejected:** `sigma plugin install --force-install`; a single toolchain on pySigma 1.x (lint would lose ATT&CK v19 validation).
- **Revisit:** move conversion to pySigma 2.x once both backends support it; diff the converted output before and after.

## DD-028 · Shell executor for the CI runner (for now)

- **Decision:** GitLab Runner on `ctl01` uses the shell executor, registered as a tagged instance runner that doesn't pick up untagged jobs.
- **Why:** an 8 GB host already running GitLab can't spare RAM for Docker images per job. The pipeline's tools (`sigma-cli`, `curl` to the Kibana API) run fine natively.
- **Risk accepted:** jobs run as `gitlab-runner` directly on the host with no isolation, so any committed `.gitlab-ci.yml` can execute code on `ctl01`. Acceptable while the GitLab instance is private, sign-up is off and I'm the only committer.
- **Revisit:** move to the Docker executor before accepting outside contributions or running untrusted code.

## DD-027 · Two independent endpoint telemetry sources

- **Decision:** a domain-wide GPO enables the Advanced Audit Policy, command lines in 4688 and PowerShell module and script block logging, alongside Sysmon.
- **Why:** each ATT&CK technique needs specific data sources, and many are off by default in Windows (4688, 4769, 4104). Sysmon is a driver an admin-level attacker can unload; the Security log is built in and clearing it raises its own event (1102). One action recorded by both means an attacker must defeat both. Public Sigma rules are written for one source or the other, so both widen what can be reused.
- **Detail:** "force subcategory override" is enabled so legacy category settings can't silently override the advanced ones.

## DD-026 · One management host outside the hypervisor

- **Decision:** mini PC 2 runs GitLab CE, its runner, Terraform and Ansible in VLAN 10.
- **Rejected:** a control-node VM on Proxmox. It would go down with the host it manages, and the G5 has no RAM for GitLab.
- **Why:** the management plane must survive the thing it manages, the same principle as DD-010. Uses idle hardware; GitLab is tuned for low memory to fit 8 GB.

## DD-025 · GitLab CE as source of truth, GitHub as public mirror

- **Decision:** detection-as-code lives in a self-hosted GitLab CE inside the lab. Its CI lints and converts Sigma rules and deploys them to Kibana; a push mirror publishes every commit to GitHub.
- **Why:** pipelines and deployment run entirely inside the lab, so no public repository can ever execute code on the network. GitHub keeps the work visible to employers: rules, commit history and `.gitlab-ci.yml`, plus pipeline evidence in the build log.
- **Rejected:** a GitHub self-hosted runner on a public repo (GitHub advises against it), and a private-only repo (invisible to recruiters). Supersedes the earlier pull-based GitHub plan.
- **Rule:** never edit on GitHub; the mirror only flows GitLab → GitHub.
- **Costs accepted:** patching and backing up GitLab; an Elastic Agent on it turns its audit logs into a detection source.

## DD-024 · No RDP from the domain controller to workstations

- **Decision:** workstations are administered from the laptop (port forwards), never by RDP from DC01.
- **Why:** it would need a SERVERS → CLIENTS firewall hole, and using a domain controller as a jump host leaves Domain Admin credentials in workstation memory, where they can be harvested. Microsoft's AD tiering model exists to prevent exactly this.
- **Follow-up:** a separate workstation-admin account instead of Domain Admin for client machines.

## DD-023 · Telemetry baseline: System + Windows integrations, sysmon-modular, no EDR yet

- **Decision:** the `Windows endpoints` agent policy carries the System and Windows integrations with Elastic's default event IDs; Sysmon uses the sysmon-modular standard config; Elastic Defend is off.
- **Why:** Elastic's defaults are already curated, and dropping events at collection loses them for investigations. sysmon-modular is widely used and ATT&CK-mapped. Defend would block the attacks the lab exists to observe; it gets its own decision once the first scenarios work.

## DD-022 · Fleet Server via Quick Start with a self-signed certificate (temporary)

- **Decision:** Fleet Server runs on `elastic01` using Kibana's Quick Start, which generates a self-signed certificate for port 8220. Agents enroll with `--insecure`.
- **Why:** gets telemetry flowing fast. `--insecure` skips identity verification only; the traffic is still encrypted.
- **Replace with:** a Fleet Server certificate issued by Elasticsearch's CA (`elasticsearch-certutil`), installed via the Advanced setup, with agents trusting that CA.

## DD-021 · Elasticsearch heap fixed at 4 GB on a 10 GB VM

- **Decision:** Elasticsearch, Kibana and (next) Fleet Server share one 10 GB VM, with the Elasticsearch heap fixed at 4 GB.
- **Why:** the rest is needed by Kibana (about 1 GB), Fleet Server and the OS, and the operating system's file cache, which Elasticsearch relies on for fast searches. Auto-sizing would not account for the other services on the same VM.
- **Revisit if:** searches slow down or circuit-breaker errors appear once all agents report.

## DD-020 · Mini PC 2 becomes the automation control node

- **Decision:** mini PC 2 will run Terraform and Ansible from the MGMT zone (VLAN 10, switch port Fa0/1).
- **Why:** Ansible runs natively on Linux, the lab's credentials and API tokens stay inside the lab instead of on my everyday laptop, and a dedicated management host mirrors how real environments separate the management plane. It also gives the OPNsense GUI a home inside VLAN 10, replacing the temporary WAN admin rule (DD-012).
- **Status:** planned.

## DD-019 · Switch managed from the console, with an address on VLAN 10

- **Decision:** the switch's only IP is `10.10.10.2` on `Vlan10` (gateway `10.10.10.1`). `Vlan1` is shut down, the web GUI is off, and SSH is not set up yet.
- **Why:** the address exists so the switch can send logs and sync time through OPNsense, not for remote logins. Console-only management removes the remote attack surface entirely until SSH is configured properly.

## DD-018 · Windows 11 template from a sysprepped copy

- **Decision:** the original Windows 11 VM (130) stays as WS01. A full clone (VM 9000 `tpl-win11-ent`) was generalized with sysprep and converted to a Proxmox template; WS02 and future clients are cloned from it.
- **Why:** sysprep gives each clone its own machine SID, so the original and the clones coexist safely. The template makes the 90-day evaluation expiry a quick re-clone instead of a reinstall, and gives Terraform something to clone later.
- **Known gap:** clones share the template's local admin password. Windows LAPS is the planned fix.

## DD-017 · Domain name `cybereli.local`

- **Decision:** the AD forest is `cybereli.local` (NetBIOS `CYBERELI`).
- **Trade-off:** Microsoft recommends a subdomain of a registered domain (for example `ad.example.com`), because `.local` overlaps with multicast DNS (mDNS). For an isolated lab with no Apple devices or mDNS clients inside it, `.local` is simpler and common.

## DD-016 · Firewall baseline first, service rules with each VM

- **Decision:** every zone gets the same baseline (DNS and ping to its own gateway, block home, block RFC1918, allow internet) before any VM is built. Rules for a specific service go in on the day the VM that provides it is built.
- **Why:** new VMs need working DNS and internet the moment they boot (Server eval must activate within 10 days). A "temporary allow-all" tends to stay, and a stable policy before the SIEM exists gives clean baseline telemetry. Service rules written with their VM are tested immediately.
- **Detail:** DNS and ICMP rules target the zone's own interface address, not "This Firewall", so a zone can't reach the firewall's other interfaces.

## DD-015 · Evaluation licensing only

- **Decision:** Windows Server 2022 Standard Evaluation and Windows 11 Enterprise Evaluation from Microsoft. No borrowed or shared product keys.
- **Why:** keys from someone else's student or work program aren't licensed for my use, and a public portfolio lab should be clean. Eval expiry is handled by rearm or by rebuilding from a template (later Terraform); an eval Server converts in place if I ever buy a license.

## DD-014 · Kali stays physical (mini PC 1)

- **Decision:** Kali runs bare metal on a mini PC in VLAN 50 (Fa0/19), not as a container or VM on the G5. Installed on mini PC 1 (the former Wazuh box) on 2026-10-26.
- **Rejected, container:** LXC shares the Proxmox kernel and attack tooling needs low-level network access, which means a privileged container one step from the hypervisor.
- **Rejected, VM:** the G5 is at 26 of 32 GB; a 4 GB Kali VM would leave the host about 2 GB.
- **Why physical:** it's the only lab traffic that crosses the switch trunk, which proves VLAN 50 end to end, and a rogue device on a switch port is a realistic scenario.

## DD-013 · IPv4-only lab

- **Decision:** IPv6 disabled on the OPNsense WAN; no IPv6 on lab interfaces.
- **Why:** one address family means one rule set to write, test and document. The ISP hands out IPv6 via SLAAC, which would otherwise need a parallel v6 policy.
- **Revisit if:** a scenario specifically needs IPv6 attack paths.

## DD-012 · OPNsense admin over WAN from a single host (temporary)

- **Decision:** a WAN rule allows only my laptop (`10.0.0.18/32`) to reach the OPNsense GUI on 443. *Disable reply-to* is enabled.
- **Why:** the laptop lives on the home network, and the firewall's management interface is in VLAN 10. Reply-to had to go because WAN rules route replies via the WAN gateway, which breaks clients on the same subnet as WAN. With a single WAN uplink, reply-to adds nothing.
- **Replace with:** an access port in VLAN 10 for admin, then remove the WAN rule.

## DD-011 · Dnsmasq for DHCP

- **Decision:** Dnsmasq serves DHCP on CLIENTS, DMZ and ATTACKER. ISC DHCP stays disabled everywhere.
- **Why:** ISC DHCP is end-of-life upstream and being phased out of OPNsense. Dnsmasq is the default for networks this size. Servers, management and SOC stay static.

## DD-010 · Proxmox management stays on the home network

- **Decision:** Proxmox management lives on VLAN 100 (`10.0.0.90`), not behind OPNsense.
- **Why:** OPNsense is a VM on that same host. If the firewall VM fails to boot or a rule goes wrong, management behind it would lock me out of the only tool that can fix it.
- **Trade-off:** the hypervisor is reachable from the home LAN. Mitigated by keeping the home network trusted and never exposing the lab to the internet.

## DD-009 · Elastic Security replaces Wazuh as the SIEM

- **Decision:** Elasticsearch + Kibana + Fleet Server as a 10 GB VM on the G5 in VLAN 60, with Elastic Agent on every endpoint. Wazuh is retired.
- **Why:** no official Sigma backend exists for Wazuh rules, so every detection would be hand-translated. Elastic has a maintained pySigma backend, a free detection engine with EQL sequence rules, a free EDR (Elastic Defend), and far more presence in job postings.
- **Runner-up:** OpenSearch Security Analytics (native Sigma import, Apache 2.0).
- **Rejected:** Security Onion (too heavy), Splunk Free (alerting disabled), Graylog Open (Sigma in paid editions), LimaCharlie (2 endpoints, cloud only), Grafana Loki (weak Windows fit).
- **Trade-offs:** Elastic License instead of Apache 2.0; loses Wazuh FIM, active response and compliance checks.
- **Reversible:** Sigma stays the source of truth, so rules move to another backend without a rewrite.
- **Write-up:** [Why I moved the lab from Wazuh to Elastic Security](2026-10-20-why-elastic-over-wazuh.md)

## DD-008 · Kali runs bare metal on a mini PC

- **Decision:** Kali on a mini PC in VLAN 50 (switch port Fa0/19), not as a VM on the G5. Ended up on mini PC 1 (see DD-014).
- **Why:** it frees 4 GB of hypervisor RAM, and a physical attacker on its own switch port mirrors a real rogue device on the network.
- **Trade-off:** no Proxmox snapshots for Kali. That's acceptable, since the targets get snapshotted before each scenario, not the attacker.

## DD-007 · Windows images from the Microsoft Evaluation Center only

- **Decision:** Windows Server 2022 for DC01 and Windows 11 Enterprise for workstations, both evaluation ISOs from Microsoft. SHA256 recorded for every ISO.
- **Why Server 2022 over 2025:** most AD attack tooling and references assume 2019/2022 defaults. 2025's hardened defaults are worth testing later as a "same attack, two outcomes" scenario on a member server.
- **Why Enterprise:** consumer ISOs install Home/Pro, and Home cannot join a domain.
- **Rejected:** third-party ISO mirrors, which are an unverifiable supply-chain risk.

## DD-006 · Default-deny segmentation with OPNsense as the only router

- **Decision:** six lab VLANs (Mgmt, Servers, Clients, DMZ, Attacker, SOC) behind OPNsense, with default deny between all of them.
- **Why:** every cross-zone action is logged and has to be explicitly allowed, so the attack path is realistic (attacker → DMZ → pivot) and fully observable.
- **Key rules:** attacker reaches only the DMZ by default; no lab VLAN can reach the home LAN; all lab zones can reach the SIEM (originally Wazuh on TCP 1514/1515; now Elastic Fleet on TCP 8220 and Elasticsearch on TCP 9200).

## DD-005 · Keep the Cisco WS-C2950G-24-EI

- **Decision:** keep the existing switch and add 1000BASE-T GBICs for the trunk and uplink.
- **Why:** inter-VM traffic stays inside Proxmox and never touches the switch, and agent log traffic is small, so 100 Mbps access ports are enough. The switch also provides real Cisco IOS configuration evidence.
- **Hardening:** native VLAN 999 on the trunk, DTP disabled, unused ports shut down in VLAN 999, BPDU guard on access ports.
- **Revisit if:** a second hypervisor is added or bulk transfers become a bottleneck.

## DD-004 · Wazuh indexer heap at 2 GB

> **Superseded by DD-009.**

- **Decision:** 2 GB heap on the 8 GB all-in-one Wazuh host.
- **Why:** balances the indexer against the manager, dashboard and OS file cache (details in the [2026-10-19 log](../00-build/2026-10-19/log.md)).

## DD-003 · Wazuh on dedicated hardware

> **Superseded by DD-009.**

- **Decision:** Wazuh all-in-one on mini PC 1 in its own SOC VLAN, not as a VM.
- **Why:** the indexer is the biggest RAM consumer in the lab. Keeping it off the G5 lets every lab VM run at once, and the SOC sits in its own zone that attackers can't reach.

## DD-002 · Wazuh instead of Microsoft Sentinel

> **Superseded by DD-009.**

- **Decision:** Wazuh as the SIEM/XDR at home.
- **Why:** no Sentinel license outside work. Detections are written in Sigma first and converted to both Wazuh rules and KQL, so the Microsoft skill set stays visible in the repo.

## DD-001 · Single Proxmox hypervisor

- **Decision:** the Dell G5 (i5-10400F, 32 GB RAM) runs Proxmox VE and hosts the firewall, domain and targets.
- **Rejected:** a two-node lab split across the mini PCs. Segmented networks between machines are far simpler inside one hypervisor's virtual switching, and the mini PCs are too small to host Windows VMs.
- **Storage:** OS plus core VMs on disk 1, lab VMs on a second LVM-thin pool on disk 2. ZFS was skipped because of mismatched disks and its RAM overhead on a 32 GB host.
