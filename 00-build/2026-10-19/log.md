# Build Log · through 2026-10-19

[Build log index](../build-log.md) · [← 2026-10-17](../2026-10-17/log.md) · [2026-10-20 →](../2026-10-20/log.md)

Cumulative log: every day from 2026-10-17 up to and including 2026-10-19. Newest day last.

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
