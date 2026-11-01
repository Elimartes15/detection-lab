# Firewall Policy (OPNsense)

**Status (2026-10-26):** baseline implemented and tested on every zone (SERVERS, CLIENTS, DMZ, ATTACKER, SOC). ATTACKER verified from the physical Kali host (`10.10.50.10`).

Baseline policy for every lab zone. Service rules (AD to DC01, Elastic ingest to the SIEM) are added when the VM that needs them is built, so each rule is tested on the day it's written.

## Principles

- **Default deny.** OPNsense blocks anything not explicitly allowed, and logs it.
- **A zone only talks to its own gateway.** DNS and ping go to the zone's interface address, not to "This Firewall", so a zone can't probe the firewall's other interfaces.
- **The home network is off-limits.** Every lab zone blocks `10.0.0.0/24`, logged, as its own rule so a lab-to-home attempt is a distinct detection signal.
- **No cross-lab by default.** Lab zones reach the internet, but not each other, unless a rule says so.
- **Rules are evaluated top to bottom; first match wins.**

## Aliases

| Alias | Type | Value |
| --- | --- | --- |
| `Home_ROGERS` | Network | `10.0.0.0/24` |
| `LAB_NETS` | Network | `10.10.0.0/16` |
| `RFC1918` | Network | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |
| `AD_Ports` | Port(s) | 53, 88, 135, 389, 445, 464, 636, 3268, 3269, 49152:65535 |
| `Fleet_Ports` | Port(s) | 8220, 9200 |

## Baseline: SERVERS (20), CLIENTS (30), DMZ (40), SOC (60)

The same five rules on each interface. Replace `<ZONE>` with the interface name.

| # | Action | Proto | Source | Destination | Port | Log | Description |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Pass | TCP/UDP | `<ZONE> net` | `<ZONE> address` | 53 | | DNS to own gateway |
| 2 | Pass | ICMP | `<ZONE> net` | `<ZONE> address` | | | Ping own gateway |
| 3 | Block | any | `<ZONE> net` | `Home_ROGERS` | | ✓ | Lab to home: never |
| 4 | Block | any | `<ZONE> net` | `RFC1918` | | ✓ | No cross-zone by default |
| 5 | Pass | any | `<ZONE> net` | any | | | Internet |

DHCP needs no rule. OPNsense allows it automatically on interfaces where Dnsmasq serves leases.

## ATTACKER (50)

| # | Action | Proto | Source | Destination | Port | Log | Description |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Pass | TCP/UDP | `ATTACKER net` | `ATTACKER address` | 53 | | DNS to own gateway |
| 2 | Pass | ICMP | `ATTACKER net` | `ATTACKER address` | | | Ping own gateway |
| 3 | Pass | any | `ATTACKER net` | `DMZ net` | | ✓ | The DMZ is the target |
| 4 | Block | any | `ATTACKER net` | `LAB_NETS` | | ✓ | Lateral movement attempt |
| 5 | Block | any | `ATTACKER net` | `Home_ROGERS` | | ✓ | Lab to home: never |
| 6 | Block | any | `ATTACKER net` | `RFC1918` | | ✓ | Any other private range |
| 7 | Pass | any | `ATTACKER net` | any | | | Internet for tooling |

Rule 4 is the key detection signal: anything from the attacker zone reaching for servers, clients or the SIEM is blocked and logged.

## MGMT (10)

Unchanged for now (OPNsense's default LAN allow rule). Tightened when the automation control node moves into VLAN 10.

## Service rules (added with their VMs)

| Added with | Zone | Destination | Ports | Purpose |
| --- | --- | --- | --- | --- |
| Elastic SIEM VM | SERVERS, CLIENTS | `10.10.60.10` | TCP `Fleet_Ports` | Agent check-in and data. **Implemented 2026-10-29.** DMZ and ATTACKER get it when their hosts get agents |
| DC01 | CLIENTS | `10.10.20.10` | `AD_Ports` (TCP/UDP) | AD. **Implemented 2026-10-24** as CLIENTS rule 3 |
| DC01 | CLIENTS | — | — | DHCP options: `dns-server [6]` = `10.10.20.10`, `domain-name [15]` = `cybereli.local`. **Done 2026-10-26** |

Service rules go **above** rule 3 in each zone, since first match wins.

## Verification

Run from the Alpine test container (CT 101), re-tagged per zone.

**CLIENTS (tag 30):**

```
udhcpc -i eth0
ping -c2 10.10.30.1     # works: own gateway
ping -c2 1.1.1.1        # works: internet
nslookup github.com     # works: DNS through the gateway
ping -c2 10.0.0.1       # fails: home blocked (rule 3, logged)
ping -c2 10.10.20.1     # fails: another zone's gateway (rule 4, logged)
```

**ATTACKER (tag 50):**

```
ping -c2 10.10.50.1     # works: own gateway
ping -c2 1.1.1.1        # works: internet
ping -c2 10.10.20.10    # fails: lateral movement (rule 4)
```

The proof is the log: Live View must show a block on ATTACKER from `10.10.50.10` for each destination, with the rule description as its label. Verified 2026-10-26 (home block labelled; the lab-zone block needs its description added).

The ATTACKER → DMZ allow can only be verified once a DMZ host exists.

## WAN exceptions (admin from the laptop)

Temporary, single-host access from `10.0.0.18/32` until administration moves to the control node in VLAN 10.

| Type | Match | Target | Purpose |
| --- | --- | --- | --- |
| WAN rule | TCP → This Firewall:443 | OPNsense GUI | Firewall admin (DD-012) |
| Port forward | TCP → `10.0.0.91:2222` | `10.10.60.10:22` | SSH to `elastic01` |
| Port forward | TCP → `10.0.0.91:5601` | `10.10.60.10:5601` | Kibana |
| Port forward | TCP → `10.0.0.91:33891` | `10.10.20.10:3389` | RDP to DC01 |
| Port forward | TCP → `10.0.0.91:33892` | `10.10.30.21:3389` | RDP to WS01 |
| Port forward | TCP → `10.0.0.91:33893` | `10.10.30.22:3389` | RDP to WS02 |

