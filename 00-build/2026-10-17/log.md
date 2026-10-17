# Build Log · through 2026-10-17

[Build log index](../build-log.md) · [2026-10-19 →](../2026-10-19/log.md)

Cumulative log: every day from 2026-10-17 up to and including 2026-10-17. Newest day last.

---

## 2026-10-17 · Planning

### Planning

- Designed the lab architecture: single Proxmox hypervisor (Dell G5), OPNsense as the only router between six lab VLANs, Wazuh and Kali on dedicated mini PCs, and the old Cisco 2950 as the core switch.
- Sized the hypervisor against its 32 GB RAM limit. Moving Wazuh and Kali off the G5 frees about 12 GB, so every lab VM can run at once (16 GB of VMs plus host overhead).
- Chose OS versions and sources.
