# Switch Configuration (Cisco WS-C2950G-24-EI · SW_Eli)

Interface and management configuration as of 2026-10-26. Credentials and unrelated legacy settings are left out.

## Port map

| Port | Description | Mode | Connects to |
| --- | --- | --- | --- |
| Fa0/3 | TRUNK-PVE01 | 802.1Q trunk, native 999, allowed 10,20,30,40,50,60,100, DTP off | Dell G5 (`nic0`) |
| Fa0/19 | KALI | Access VLAN 50, portfast, BPDU guard | Mini PC 1 (Kali, `10.10.50.10`) |
| Fa0/20 | CTL01 | Access VLAN 10, portfast, BPDU guard | Mini PC 2 (`ctl01`, GitLab, `10.10.10.20`) |
| Fa0/24 | UPLINK-MODEM | Access VLAN 100, portfast | Home router |
| Fa0/1–2, Fa0/4–18, Fa0/21–23, Gi0/1–2 | UNUSED | Access VLAN 999 | Shut down |

## VLANs

| VLAN | Name |
| --- | --- |
| 10 | MGMT |
| 20 | SERVERS |
| 30 | CLIENTS |
| 40 | DMZ |
| 50 | ATTACKER |
| 60 | SOC |
| 100 | HOME |
| 999 | DEAD (native VLAN on the trunk, unused ports) |

## Configuration

```
interface FastEthernet0/3
 description TRUNK-PVE01
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,20,30,40,50,60,100
 switchport mode trunk
 switchport nonegotiate
!
interface FastEthernet0/19
 description KALI
 switchport access vlan 50
 switchport mode access
 spanning-tree portfast
 spanning-tree bpduguard enable
!
interface FastEthernet0/20
 description CTL01
 switchport access vlan 10
 switchport mode access
 switchport nonegotiate
 spanning-tree portfast
 spanning-tree bpduguard enable
!
interface FastEthernet0/24
 description UPLINK-MODEM
 switchport access vlan 100
 switchport mode access
 spanning-tree portfast
!
! Every unused port (Fa0/1-2, Fa0/4-18, Fa0/21-23, Gi0/1-2):
interface <unused port>
 description UNUSED
 switchport access vlan 999
 switchport mode access
 shutdown
!
interface Vlan1
 no ip address
 shutdown
!
interface Vlan10
 description MGMT
 ip address 10.10.10.2 255.255.255.0
!
ip default-gateway 10.10.10.1
no ip http server
```

## Hardening choices

| Setting | Why |
| --- | --- |
| Native VLAN 999 on the trunk | Untagged frames land in a VLAN that goes nowhere, which blocks VLAN-hopping by double tagging |
| `switchport nonegotiate` on the trunk | DTP off: a device on the trunk can't negotiate its way into other VLANs |
| Unused ports in VLAN 999 and shut down | A cable plugged into a spare port gets nothing |
| BPDU guard on the Kali port | If anything on that port sends spanning-tree frames (a rogue switch, or an attack tool), the port shuts itself down |
| No BPDU guard on the modem uplink | Some home routers send BPDUs; guard would disable the uplink |
| `Vlan1` shut, management on `Vlan10` | The switch's own address lives in the management zone, not the default VLAN |
| `no ip http server` | Removes the old, unencrypted web management interface |

Remote management (SSH) is not configured yet; the switch is managed from the console.
