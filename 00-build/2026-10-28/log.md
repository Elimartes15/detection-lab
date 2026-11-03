# Build Log · through 2026-10-28

[Build log index](../build-log.md) · [← 2026-10-26](../2026-10-26/log.md) · [2026-10-29 →](../2026-10-29/log.md)

Cumulative log: every day from 2026-10-17 up to and including 2026-10-28. Newest day last.

---

## 2026-10-17 · Planning

### Planning

- Designed the lab architecture: single Proxmox hypervisor (Dell G5), OPNsense as the only router between six lab VLANs, Wazuh and Kali on dedicated mini PCs, and the old Cisco 2950 as the core switch.
- Sized the hypervisor against its 32 GB RAM limit. Moving Wazuh and Kali off the G5 frees about 12 GB, so every lab VM can run at once (16 GB of VMs plus host overhead).
- Chose OS versions and sources.

---

## 2026-10-19 · Wazuh and Proxmox

### Wazuh on mini PC 1

> **Superseded on 2026-10-20:** Wazuh was replaced by Elastic Security. Kept here as a record of the evaluation. See [why Elastic over Wazuh](../../docs/2026-10-20-why-elastic-over-wazuh.md).

**OS install**

- Ubuntu Server LTS, **standard install** (not minimized). Minimized strips editors and troubleshooting tools I'd reinstall while debugging, and saves only about 100 MB of RAM.
- OpenSSH server enabled during install, so the box is managed over SSH.
- Network: DHCP on the home LAN, planned to move to `10.10.60.10` on VLAN 60.
- Disk: `<disk size>`, LVM, root logical volume `<expanded to full disk: yes/no>`.
- Fully updated after install:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

**Wazuh install**

- Wazuh `4.14`, all-in-one (manager, indexer, dashboard) using the official quickstart installation assistant.
- Admin password saved to my password manager.
- No agents were enrolled.

**Indexer JVM heap: 2 GB**

The default guidance is half of RAM, but that assumes the indexer has the machine to itself. On an 8 GB all-in-one, the RAM is shared:

| Component | RAM |
| --- | --- |
| Ubuntu | ~0.5 GB |
| Wazuh manager | ~0.5–1 GB |
| Dashboard | ~0.5–1 GB |
| Indexer heap | 2 GB |
| OS file cache (used by the indexer for search) | ~3–4 GB |

1 GB risks circuit-breaker errors once all agents are reporting; 4 GB would starve the manager and dashboard. Set in `/etc/wazuh-indexer/jvm.options`:

```
-Xms2g
-Xmx2g
```

**Proxmox installer USB**

- Reused the Ubuntu USB. Rufus overwrites the whole drive, so no manual wipe was needed.
- Proxmox VE `9.2.2` ISO from proxmox.com. SHA256 `4e88fe416df9b527624a175f24c9aa07c714d3332afb1ee3dbf3879573ef2c6c` matched the published value.
- Rufus settings: GPT, UEFI, **DD Image mode**. The Proxmox installer doesn't boot reliably from Rufus's default ISO mode.
- Dismissed Windows' "You need to format the disk" prompt after writing.

### Proxmox VE on the Dell G5

**BIOS (F2)**

- Storage mode set to **AHCI**. Dell ships in RAID/Intel RST mode, which hides the SSDs from the Linux installer.
- **Intel Virtualization Technology (VT-x)** and **VT for Direct I/O (VT-d)** enabled.
- Booted the USB from the F12 one-time boot menu.

**Install**

- Proxmox VE `<version>`, graphical installer.
- Target: disk 1, **ext4**. Disk 2 is left for a separate LVM-thin pool for lab VMs.
- Hostname `pve01.lab.local`.
- Management IP: static `10.0.0.90/24`, set manually in place of the DHCP address the installer pre-filled.
- Installer USB removed after the install and kept as a rescue disk.

**First-boot issue**

- The console showed repeated `EXT4-fs error ... Detected aborted journal`, and the console login then hung.
- Meaning: the kernel hit write errors, set the root filesystem read-only, then lost access to the disk.
- A hard reboot came back clean.
- Suspected cause: NVMe power-state (APST) dropout, a known Linux issue on some SSDs. A failing or loosely seated drive hasn't been ruled out yet.

Follow-up checks:

```bash
mount | grep " / "                                          # root must be rw
dmesg | grep -iE "ext4|nvme|ata|i/o error|reset|timeout"    # no errors this boot
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINT                    # confirm NVMe vs SATA
smartctl -a /dev/nvme0                                      # Critical Warning 0x00, Media Errors 0
```

If NVMe, disable deep power states in `/etc/default/grub`, then run `update-grub` and reboot:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet nvme_core.default_ps_max_latency_us=0 pcie_aspm=off"
```

Result: everything showed normal after reboot.

### Issues and fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| `EXT4-fs error: Detected aborted journal` on first boot; root went read-only and console login hung | Suspected NVMe APST power-state dropout | Hard reboot |

---

## 2026-10-20 · SIEM decision

### SIEM decision: Elastic Security replaces Wazuh

**What changed**

| Area | Before | Now |
| --- | --- | --- |
| SIEM | Wazuh all-in-one on mini PC 1 | Elasticsearch + Kibana + Fleet Server, VM on the G5, VLAN 60, 10 GB RAM |
| Endpoint agent | Wazuh agent | Elastic Agent (Windows, Sysmon, PowerShell integrations; Elastic Defend optional) |
| Network logs | Syslog to Wazuh | Elastic Agent OPNsense and Cisco integrations |
| Sigma | Hand-translated to Wazuh XML | `sigma convert` with the Elasticsearch backend → Kibana detection rules via CI |
| YARA | Wazuh FIM + active response | Rules CI-tested in the repo; scheduled scan writes matches to the event log, Elastic Agent ships them |
| Mini PC 1 | Wazuh host | Freed: second DMZ Linux target or spare |

**Why:** there is no official Sigma backend for Wazuh's rule format, so every detection would have been translated by hand. Elastic has a maintained pySigma backend, a free Basic tier with a full detection engine, and a free EDR. Full reasoning in [why Elastic over Wazuh](../../docs/2026-10-20-why-elastic-over-wazuh.md).

**Alternatives evaluated:** OpenSearch Security Analytics (runner-up), Security Onion, Splunk Free, Graylog Open, LimaCharlie, Grafana Loki.

**G5 RAM budget after the change**

| VM | RAM |
| --- | --- |
| OPNsense | 2 GB |
| DC01 | 4 GB |
| WS01 | 4 GB |
| WS02 | 4 GB |
| Ubuntu DMZ web | 2 GB |
| Elastic SIEM | 10 GB |
| **Total** | **26 GB** |
| Headroom for Proxmox host (of 32 GB) | 6 GB |

**Next**

- No-subscription repo and updates, wipe disk 2 and create the `vm-lab` LVM-thin pool, ISO downloads (add Ubuntu Server for the Elastic VM).
- switch config and VLAN-aware bridge, moving management to VLAN 100 in staged steps.
- Mini PC 1: reimage once its new role is decided.

---

## 2026-10-21 · Network build

### Disk health, storage, switch, OPNsense, DHCP

**Home network reference**

| Item | Value |
| --- | --- |
| Home subnet | `10.0.0.0/24` |
| Home router | `10.0.0.1` |
| Router DHCP range | `10.0.0.2–10.0.0.80` |
| Proxmox management (`pve01`) | `10.0.0.90`, static |
| OPNsense WAN | `10.0.0.91`, static (also reserved on the router) |

**Disk health** (`smartctl -a`, `dmesg`)

| Disk | Role | Result |
| --- | --- | --- |
| Samsung PM991a 512 GB NVMe | Proxmox OS + `local-lvm` | SMART PASSED; critical warning `0x00`; 0 media/integrity errors; 7% used; 6,775 power-on hours |
| Toshiba KSG60ZSE 512 GB SATA SSD | `vm-lab` pool | SMART PASSED; 0 reallocated, 0 uncorrectable, 0 CRC errors; 16% wear; 24,589 power-on hours |

- No new ext4 or I/O errors in `dmesg`. The `orphan cleanup on readonly fs` line at boot is the recovery from Monday's hard reboot.
- The Toshiba's SMART log holds 3 old ATA errors (aborted feature commands during boot-time identification, the last at 24,061 hours). Benign, nothing current.
- The OS disk is the NVMe, and it exposes deep power states (PS3/PS4) with up to 9 ms exit latency. That fits the APST explanation for Monday's error.

**Storage**

- `sda` (Toshiba) wiped of its old Windows partitions and created as the LVM-thin pool `vm-lab` for lab VMs and containers.

**Switch (Cisco WS-C2950G-24-EI, hostname `SW_Eli`)**

| Port | Description | Mode | Connects to |
| --- | --- | --- | --- |
| Fa0/3 | PROXMOX | Trunk, native 999, allowed 10,20,30,40,50,60,100, DTP off | Dell G5 (`nic0`) |
| Fa0/24 | UPLINK-MODEM | Access VLAN 100 | Home router |
| Fa0/22 | — | Access VLAN 30 | Not connected |
| All others | — | VLAN 1 | Not connected (hardening pending) |

- VLANs created: 10 MGMT, 20 SERVERS, 30 CLIENTS, 40 DMZ, 50 ATTACKER, 60 SOC, 100 HOME, 999 DEAD.
- Both connected links negotiated 100 Mbps full duplex, so there is no duplex mismatch.
- The Gi0/1 and Gi0/2 slots hold **1000BASE-SX** (multimode fiber) GBICs. A gigabit copper trunk to the G5 needs 1000BASE-T GBICs (WS-G5483) instead.
- Config saved with `write memory`.

```
SW_Eli#show interfaces trunk
Port        Mode         Encapsulation  Status        Native vlan
Fa0/3       on           802.1q         trunking      999

Port        Vlans allowed on trunk
Fa0/3       10,20,30,40,50,60,100
```

Pending hardening: move unused ports to VLAN 999 and shut them down; shut down `interface Vlan1`.

**Proxmox networking**

- Backed up `/etc/network/interfaces` to `/root/interfaces.bak` before changing it.
- Physical NIC is `nic0` (Proxmox pinned interface names).
- `vmbr0` made VLAN-aware. Management moved to tagged VLAN 100 at `10.0.0.90/24`, since untagged traffic now lands in the dead native VLAN 999.

**OPNsense 25.7 (VM 100)**

- UFS install on a 20 GB virtual disk. UFS chosen over ZFS for a 2 GB RAM firewall.
- Two VirtIO NICs on `vmbr0`: `vtnet0` tagged 100 (WAN) and `vtnet1` untagged (trunk for every lab VLAN).

| Interface | Device | Address |
| --- | --- | --- |
| WAN | `vtnet0` (Proxmox tag 100) | `10.0.0.91/24`, gateway `10.0.0.1`, IPv6 disabled |
| LAN (MGMT) | `vtnet1` VLAN 10 | `10.10.10.1/24` |
| SERVERS | `vtnet1` VLAN 20 | `10.10.20.1/24` |
| CLIENTS | `vtnet1` VLAN 30 | `10.10.30.1/24` |
| DMZ | `vtnet1` VLAN 40 | `10.10.40.1/24` |
| ATTACKER | `vtnet1` VLAN 50 | `10.10.50.1/24` |
| SOC | `vtnet1` VLAN 60 | `10.10.60.1/24` |

- WAN: *Block private networks* and *Block bogon networks* unticked, because the WAN is an RFC1918 network.
- IPv6 disabled on WAN to keep the lab IPv4-only. The installer had picked up an ISP IPv6 address via SLAAC.
- Admin access: WAN rule passing TCP from my laptop (`10.0.0.18/32`) to This Firewall on 443. A deliberate, single-host exception until admin moves to VLAN 10.
- *Firewall → Settings → Advanced → Disable reply-to* enabled. Verified in the loaded ruleset:

```
pass in quick on vtnet0 inet proto tcp from 10.0.0.18 to (self) port = https flags S/SA keep state
```

**DHCP**

- Dnsmasq, listening on CLIENTS, DMZ and ATTACKER. ISC DHCP is not used (end-of-life).
- Ranges `.100–.200` on VLANs 30, 40 and 50. Gateway and DNS are the interface IP for now; DNS moves to DC01 (`10.10.20.10`) once it exists.
- VLANs 10, 20 and 60 are static-only.

**Verification**

Alpine LXC (CT 101) on `vmbr0`, re-tagged per test:

| VLAN tag | Lease |
| --- | --- |
| 30 | `10.10.30.118` from `10.10.30.1` |
| 40 | `10.10.40.118` |
| 50 | `10.10.50.118` |

- Proves the path container → VLAN-aware bridge → `vtnet1` trunk → OPNsense VLAN interface → Dnsmasq.
- That path stays inside `vmbr0`. The switch trunk itself is proven by VLAN 100: Proxmox management and the OPNsense WAN reach the home router through Fa0/3 → Fa0/24.
- No internet or inter-VLAN traffic yet. New interfaces are default-deny until the firewall policy is written.

**Next**

- Firewall policy: default deny, lab → home block on `10.0.0.0/24`, AD ports to DC01, SIEM ingest to VLAN 60.
- Switch hardening.
- Elastic SIEM VM in VLAN 60.

### Issues and fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| Test container got no DHCP lease on VLAN 30 | Dnsmasq wasn't enabled or listening on the new VLAN interfaces | Enabled Dnsmasq and added CLIENTS, DMZ and ATTACKER to its interfaces; confirmed with `udhcpc` |
| OPNsense GUI unreachable from the home LAN over WAN | WAN rules add `reply-to (vtnet0 10.0.0.1)`, so replies went to the home router instead of the laptop on the same subnet. The rule's port range was also `any–443` | Enabled *Disable reply-to*, set the port to 443, verified with `pfctl -sr` |
| GUI dropped every time a change was applied | Applying reloads the firewall, undoing a manual `pfctl -d`, before any WAN allow rule existed | Created the WAN allow rule before applying anything else |

---

## 2026-10-22 · Planning

### Planning and documentation

- Drew the [virtual network diagrams](../../docs/virtual-network.md): topology (trunk, VLAN-aware bridge, OPNsense, VMs) and five hop-by-hop traffic flows.
- Wrote the baseline [firewall policy](../../01-network/firewall-policy.md): every zone gets DNS and ping to its own gateway, a logged home block, a logged cross-zone block, then internet.
- Decided Kali stays bare metal on mini PC 2 instead of a container or VM (DD-014).
- Started planning infrastructure as code: Terraform for VMs, Ansible for configuration. Not adopted yet.

### Next

- Build the firewall baseline.

---

## 2026-10-23 · Firewall

### Firewall baseline (started)

- OPNsense config backup downloaded before any change (kept locally, never committed: it contains password hashes and certificate keys).
- Aliases created: `Home_LAN` (`10.0.0.0/24`), `LAB_NETS` (`10.10.0.0/16`), `RFC1918` (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- Approach: baseline rules on every zone first, service rules added with the VM that needs them (DD-016). Policy in [firewall policy](../../01-network/firewall-policy.md).
- CLIENTS (VLAN 30): first rules in place: ping to own gateway, block `Home_LAN` (logged), allow internet.

### Next

- Finish CLIENTS (DNS to gateway, cross-zone block, rule order), then SERVERS, DMZ, SOC and ATTACKER.

---

## 2026-10-24 · Firewall, DC01, WS01

### Firewall baseline (CLIENTS and SERVERS completed)

- New port alias `AD_Ports`: 53, 88, 135, 389, 445, 464, 636, 3268, 3269, 49152:65535. A rule's port field takes one port or a range, so a list needs an alias.
- AD rule added early because DC01 was built the same night.
- Rules reordered so allows sit above the blocks (first match wins).

CLIENTS (VLAN 30), final order:

| # | Action | Proto | Destination | Port | Description |
| --- | --- | --- | --- | --- | --- |
| 1 | Pass | TCP/UDP | CLIENTS address | 53 | DNS to gateway |
| 2 | Pass | ICMP | CLIENTS address | | Ping own gateway |
| 3 | Pass | TCP/UDP | `10.10.20.10` | `AD_Ports` | AD to DC01 |
| 4 | Block (log) | any | `Home_LAN` | | Lab to home |
| 5 | Block (log) | any | `RFC1918` | | Cross-zone block |
| 6 | Pass | any | any | | Internet |

SERVERS (VLAN 20): the same set without the AD rule (5 rules), built by cloning the CLIENTS rules.

DMZ, SOC and ATTACKER rule sets are still pending.

### Licensing decision

- Windows evaluation media only; no borrowed product keys (DD-015).

### DC01 (VM 120)

- Windows Server 2022 **Standard Evaluation (Desktop Experience)**: Standard because Datacenter's extras are hypervisor/storage features a DC doesn't use; GUI for learning and screenshots.
- q35, OVMF (UEFI) with EFI disk, TPM 2.0, VirtIO SCSI single, 60 GB on `local-lvm` (Discard, SSD emulation, IO thread), 4 GB RAM, 2 vCPU (host), `vmbr0` tag 20.
- Storage driver loaded during setup from the VirtIO ISO (`vioscsi\2k22\amd64`); `virtio-win-guest-tools.exe` installed the network driver and QEMU agent afterwards.
- Static `10.10.20.10/24`, gateway and DNS `10.10.20.1` (DNS moves to itself after promotion). Renamed to `DC01`.
- Activated: `ServerStandardEval`, `TIMEBASED_EVAL` channel, 180 days. **Expires around 2027-04-22.**
- IPv6 left enabled: Microsoft doesn't support disabling it on domain controllers. Only link-local, never routed.
- Tests: gateway, internet and DNS work; `10.0.0.1` blocked.

### WS01 (VM 130)

- Windows 11 **Enterprise Evaluation** (90 days). A consumer ISO asked for a product key, so it was replaced with the eval (see issues).
- Same VM layout as DC01, but 64 GB on `vm-lab` and `vmbr0` tag 30. TPM 2.0 required by Windows 11.
- Setup: `vioscsi\w11\amd64` for the disk, `NetKVM\w11\amd64` loaded at the network screen, local account `labadmin`.
- DHCP lease `10.10.30.148` from `10.10.30.1`, DNS `10.10.30.1`, suffix `internal` (OPNsense default; becomes `lab.local` later).
- Tests: `8.8.8.8` replies, `github.com` resolves and replies, `10.0.0.1` times out (home block).
- Not joined to the domain yet: it may become the sysprep template for WS02.

### Next

- Promote DC01 to `lab.local`, then test `AD_Ports` from WS01 and point CLIENTS DHCP DNS at `10.10.20.10`.
- DMZ, SOC and ATTACKER rules; switch hardening; Fa0/2 to VLAN 50; Kali on mini PC 2.

### Issues and fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| Windows setup showed no disk | Windows has no driver for the VirtIO SCSI controller | Load driver from the VirtIO ISO: `vioscsi\w11\amd64` (WS01), `vioscsi\2k22\amd64` (DC01) |
| Microsoft Evaluation Center download never started after the form | A browser extension blocked the redirect | Downloaded from an incognito window |
| Windows 11 setup asked for a product key | The ISO was the consumer (Home/Pro) media | Switched to the Windows 11 Enterprise evaluation ISO |

---

## 2026-10-26 · Domain, templates, switch hardening, Kali

### Cross-zone check

- From the Windows 11 client (VLAN 30), `ping 10.10.20.10` timed out, and OPNsense Live View logged the block on CLIENTS with the label **RFC1918 Block**. First logged proof that zones are separated.

### Firewall baseline completed

- ATTACKER, SOC and DMZ rule sets built (CLIENTS and SERVERS were done on 2026-10-24). Every lab zone now has the baseline policy. Details in [firewall policy](../../01-network/firewall-policy.md).
- DMZ needs no rule for traffic from Kali: the ATTACKER → DMZ allow lives on the ATTACKER interface, and OPNsense is stateful, so replies return automatically.

### Active Directory: `cybereli.local`

- DC01 fully patched, then snapshot `clean-pre-AD`.
- Promoted to the first domain controller of a new forest:

```powershell
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools
Install-ADDSForest -DomainName "cybereli.local" -DomainNetbiosName "CYBERELI" -InstallDns
```

- Domain name `cybereli.local` instead of the planned `lab.local` (DD-017).
- CLIENTS DHCP (Dnsmasq) options changed so clients find the domain: `dns-server [6]` = `10.10.20.10`, `domain-name [15]` = `cybereli.local`.

### Windows 11 template and second client

- Original Windows 11 VM (130) kept as **WS01**. Sysprep gives every clone a new machine SID, so the original and the clones never conflict.
- Full clone of 130 → VM **9000** `tpl-win11-ent` on `vm-lab`, generalized and converted to a Proxmox template:

```
C:\Windows\System32\Sysprep\sysprep.exe /generalize /oobe /shutdown
```

- Full clone of the template → VM **131** `WS02` (tag 30, new MAC).

### Domain join

- WS01 and WS02 joined from an elevated PowerShell:

```powershell
Add-Computer -DomainName cybereli.local -Credential CYBERELI\Administrator -Restart
```

- WS02 was first named `WS202` by mistake and renamed as a domain member, which also renames its AD object:

```powershell
Rename-Computer -NewName WS02 -DomainCredential CYBERELI\Administrator -Restart
```

- Verified on DC01:

```
PS> Get-ADComputer -Filter * | Select Name, DNSHostName
Name  DNSHostName
----  -----------
DC01  DC01.cybereli.local
WS01  WS01.cybereli.local
WS02  WS02.cybereli.local
```

### Switch hardening

| Port | Description | Mode | Status |
| --- | --- | --- | --- |
| Fa0/3 | TRUNK-PVE01 | Trunk, native 999, allowed 10,20,30,40,50,60,100, DTP off | Connected (Dell G5) |
| Fa0/19 | KALI | Access VLAN 50, portfast, BPDU guard | Connected (Kali, mini PC 1) |
| Fa0/24 | UPLINK-MODEM | Access VLAN 100, portfast | Connected (home router) |
| Fa0/1–2, Fa0/4–18, Fa0/20–23, Gi0/1–2 | UNUSED | Access VLAN 999 | Shut down |

- Kali moved to **Fa0/19** (planned as Fa0/2).
- `interface Vlan1` shut down. The switch's management address is now `10.10.10.2` on `Vlan10`, with `ip default-gateway 10.10.10.1`, so it can later send logs through OPNsense.
- Old web GUI disabled (`no ip http server`). Remote management (SSH) not set up yet; the switch is managed from the console.
- Config saved with `write memory`. Interface config in [switch config](../../01-network/switch-config.md).

### Verification

- Switch ↔ OPNsense ping on VLAN 10 in both directions. The first lab VLAN proven **across the physical trunk**, not just inside the Proxmox bridge.
- The first run from OPNsense lost its first 14 packets while the new `Vlan10` interface came up (spanning tree and ARP), then replied steadily at ~1.5 ms, TTL 255. The switch's own ping to `10.10.10.1` was 5/5.

### DNS hardening on DC01

- Forwarder confirmed: `10.10.20.1` (OPNsense). `Resolve-DnsName github.com` answers through it.
- Root hints disabled (`Set-DnsServerForwarder -UseRootHint $false`), so every DNS query in the lab leaves through one resolver. That gives one place to log and hunt DNS later.

```
UseRootHint : False
IPAddress   : 10.10.20.1
```

- Snapshots taken: DC01 `ad-promoted`, WS01 and WS02 `domain-joined`.

### Kali (mini PC 1)

- Installed bare metal on **mini PC 1** (the former Wazuh box; Wazuh is retired). Mini PC 2 becomes the automation control node (DD-020).
- Graphical install, hostname `kali01`, no domain, guided full-disk partitioning. Connected to switch port Fa0/19 (VLAN 50).
- First boot: DHCP lease in `10.10.50.x` with internet, proving the ATTACKER rules work across the physical port and trunk.
- Static address set with `nmtui`: `10.10.50.10/24`, gateway and DNS `10.10.50.1` (outside the DHCP range `.100–.200`).

### Attacker zone verification

Reachability checks from Kali (`10.10.50.10`), confirmed in OPNsense Live View:

| Destination | Result | Live View label |
| --- | --- | --- |
| `10.0.0.1` (home router) | Blocked | Not allow to cross home lan |
| `10.10.30.1` (CLIENTS gateway) | Blocked | *(empty: rule has no description yet)* |
| Internet | Allowed | — |

- The lab-zone block is working, but its rule has no description, so its log entries carry no label. Adding "Lateral movement attempt" makes these events searchable by name in the SIEM.

### Next

- Add the description to the ATTACKER `LAB_NETS` block rule.
- Build the Elastic SIEM VM in VLAN 60.

### Issues and fixes

| Issue | Cause | Fix |
| --- | --- | --- |
| `Add-Computer`: "The specified domain either does not exist or could not be contacted" | Clients still used OPNsense (`10.10.30.1`) for DNS, which doesn't know the AD domain | Dnsmasq DHCP option `dns-server [6]` = `10.10.20.10` on CLIENTS, then `ipconfig /renew` |
| DNS suffix showed `10.10.20.10` | The `domain-name [15]` option had the IP instead of the domain | Set `domain-name [15]` = `cybereli.local` |
| `Add-Computer`: "Access is denied" on WS02 | PowerShell wasn't running as administrator | Re-ran from an elevated PowerShell |
| WS02 joined as `WS202` | Typo when renaming | `Rename-Computer -DomainCredential` from the domain member |
| Gi0/1–2 still in VLAN 1 and enabled | Missed by the unused-port range command | Parked in VLAN 999 and shut down separately |
| Kali USB didn't boot | Stick was in a USB port the mini PC doesn't boot from | Moved it to another USB port, then F12 boot menu |
| `nmcli con mod`: "invalid or not allowed setting 'ipv4'" | Connection name or line break didn't parse as intended | Set the static IP with `nmtui` instead |

---

## 2026-10-28 · Elastic SIEM: Elasticsearch and Kibana

### VM 160 · `elastic01`

| Setting | Value |
| --- | --- |
| OS | Ubuntu Server 24.04 LTS (chosen over 26.04 for proven Elastic support) |
| CPU | 1 socket × 4 cores, type `host` |
| Memory | 10240 MiB, ballooning off |
| Disk | 100 GB on `vm-lab`, Discard on; root LV extended to the full disk |
| Network | `vmbr0` tag 60 (SOC), static `10.10.60.10/24`, gateway and DNS `10.10.60.1` |

- DNS points at the SOC gateway, not DC01: the SOC zone can't reach other lab zones by design.
- One socket instead of two: the G5 has a single physical CPU, and one virtual socket avoids odd NUMA behaviour in the guest.

### Admin access from the laptop

OPNsense **NAT → Port Forward** on WAN, source `10.0.0.18/32` only, each with an associated filter rule:

| WAN | → | Purpose |
| --- | --- | --- |
| `10.0.0.91:2222` | `10.10.60.10:22` | SSH to `elastic01` |
| `10.0.0.91:5601` | `10.10.60.10:5601` | Kibana |

- A single-host exception, like the WAN GUI rule (DD-012). Removed once admin moves to the control node in VLAN 10 (DD-020).

### Elasticsearch 9.5.5

- Installed from Elastic's 9.x APT repository. Security (TLS and authentication) is enabled automatically on install. The generated `elastic` password is stored in the password manager.
- `cluster.name: cybereli-siem`, `node.name: elastic01`.
- JVM heap fixed at 4 GB (`/etc/elasticsearch/jvm.options.d/heap.options`), leaving about 6 GB for Kibana, Fleet Server, the OS and the file cache Elasticsearch searches from.

```
$ curl --cacert /etc/elasticsearch/certs/http_ca.crt -u elastic https://localhost:9200
  "name" : "elastic01",
  "cluster_name" : "cybereli-siem",
  "version" : { "number" : "9.5.5", ... },
  "tagline" : "You Know, for Search"

$ curl ... "https://localhost:9200/_cat/nodes?v&h=name,heap.max"
name      heap.max
elastic01      4gb
```

### Kibana

- Encryption keys generated with `kibana-encryption-keys generate` and added to `kibana.yml`. Detection rules, alerting and Fleet need them.
- `server.host: "0.0.0.0"`, `server.publicBaseUrl: "http://10.0.0.91:5601"` (the address reached through the port forward).
- Enrolled with Elasticsearch using an enrollment token (`elasticsearch-create-enrollment-token -s kibana`) and the verification code (`kibana-verification-code`), then logged in as `elastic`.
- Backups: `kibana.yml.bak` on the VM; the three encryption keys stored in the password manager. Neither goes in the repo.
- Kibana is served over plain HTTP for now, reachable only from the laptop. HTTPS is a later hardening step.
- Snapshot `elastic-base` taken.

### Next

- Fleet Server on `elastic01`, a `Fleet_Ports` alias (8220, 9200) allowed from every zone above the blocks.
- Telemetry: Sysmon, audit policy GPO, PowerShell script-block logging, Elastic Agent on DC01, WS01, WS02.
