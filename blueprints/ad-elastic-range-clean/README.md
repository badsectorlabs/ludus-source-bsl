# Clean AD + Elastic Baseline

A Ludus blueprint providing a hardened, vulnerability-free Active Directory environment with full Elastic Security telemetry. This is a **baseline** lab — no intentional misconfigurations, no weak credentials, no exposed attack paths. Use it for detection engineering, tooling development, and training scenarios where you want a clean starting point.

## What This Deploys

| VM | Template | VLAN | IP | Purpose |
|----|----------|------|----|---------|
| `elastic` | debian-12-x64-server-template | 20 | .20.2 | Elastic SIEM + Fleet Server |
| `DC01` | win2022-server-x64-template | 10 | .10.10 | Forest root DC — ludus.local |
| `DC02` | win2022-server-x64-template | 11 | .11.10 | Child domain DC — sub.ludus.local |
| `WS01` | win11-22h2-x64-enterprise-template | 11 | .11.20 | Win11 workstation — sub.ludus.local member |
| `kali` | kali-x64-desktop-template | 99 | .99.1 | Analyst / attacker box |

**Estimated deploy time:** 40–55 minutes  
**RAM required:** ~28 GB

## Network Layout

```
VLAN 10 — ludus.local (forest root)
  DC01  10.X.10.10

VLAN 11 — sub.ludus.local (child domain)
  DC02  10.X.11.10
  WS01  10.X.11.20

VLAN 20 — Security tooling
  elastic  10.X.20.2

VLAN 99 — Attacker / analyst
  kali  10.X.99.1
```

Inter-VLAN default is **DENY**. Explicit ACCEPT rules are in place for:
- VLAN 10 ↔ VLAN 11 (AD replication, child domain promotion)
- VLAN 10/11 → VLAN 20 (Elastic agent enrollment and log shipping)
- VLAN 99 → VLAN 10/11/20 (Kali full access)

## Testing Mode (Snapshot) Behaviour

| VM | `snapshot` | `block_internet` |
|----|-----------|-----------------|
| DC01 | `true` | `true` |
| DC02 | `true` | `true` |
| WS01 | `true` | `true` |
| elastic | `false` | `false` |
| kali | `false` | `false` |

Windows VMs are snapshotted and internet-isolated when `ludus testing start` is run. The Elastic server and Kali retain internet access at all times.

## Roles Used

| Role | VM(s) | Purpose |
|------|-------|---------|
| `badsectorlabs.ludus_elastic_container` | elastic | Deploys Elasticsearch + Kibana + Fleet |
| `badsectorlabs.ludus_elastic_agent` | DC01, DC02, WS01 | Installs Elastic Agent + Sysmon |
| `badsectorlabs.ludus_windows_utils.ludus_ad_password_policy` | DC01, DC02 | Enforces strong 14-char policy with lockout |
| `badsectorlabs.ludus_windows_utils.ludus_bulk_ad_content` | DC01, DC02 | Creates minimal OUs, groups, and users |

## Access

| Service | URL / Address | Credentials |
|---------|---------------|-------------|
| Kibana | `https://10.X.20.2:5601` | `elastic` / `ElasticS3cur3!` |
| Fleet Server | `https://10.X.20.2:8220` | — |
| DC01 (RDP) | `10.X.10.10:3389` | `CORP\domainadmin` / `password` |
| DC02 (RDP) | `10.X.11.10:3389` | `SUB\domainadmin` / `password` |
| WS01 (RDP) | `10.X.11.20:3389` | `SUB\domainadmin` / `password` |
| Kali | `10.X.99.1` | `kali` / `kali` |

Replace `X` with your range's second octet (visible in `ludus range list`).

## Domain Users

### ludus.local (DC01)

| Username | Password | Groups | Notes |
|----------|----------|--------|-------|
| `ludus.admin` | `LudusAdm1n$ecure!` | Domain Admins, IT-Admins | Forest root admin |
| `ludus.user` | `LudusUs3r$ecure!` | Help-Desk | Standard user |
| `svc.monitoring` | `M0n1t0r$vc_Secure!` | — | Service account |

### sub.ludus.local (DC02)

| Username | Password | Groups | Notes |
|----------|----------|--------|-------|
| `sub.admin` | `SubAdm1n$ecure!` | Domain Admins, Sub-IT-Admins | Child domain admin |
| `sub.user` | `SubUs3r$ecure!` | — | Standard user |

## Password Policy (both domains)

| Setting | Value |
|---------|-------|
| Minimum length | 14 characters |
| Complexity | Required |
| Minimum age | 1 day |
| Maximum age | 90 days |
| History | 24 passwords |
| Lockout threshold | 5 attempts |
| Lockout duration | 30 minutes |

## Deploy Instructions

### 1. Install required roles

```bash
ludus ansible collection add badsectorlabs.ludus_windows_utils
ludus ansible role add badsectorlabs.ludus_elastic_container
ludus ansible role add badsectorlabs.ludus_elastic_agent
```

### 2. Apply and deploy

```bash
ludus range config set -f blueprints/ad-elastic-range-clean/range-config.yml
ludus range deploy
```

### 3. Monitor

```bash
ludus range logs -f       # live log stream
ludus range errors        # fatal errors only
```

### 4. Enable testing mode (snapshot + internet isolation)

```bash
ludus testing start
```

This snapshots DC01, DC02, and WS01. Kali and elastic remain running with internet access. Revert all Windows VMs to a clean state at any time:

```bash
ludus testing stop   # reverts snapshots
ludus testing start  # re-snapshots for a fresh round
```

## Idempotency

All roles used in this blueprint are fully idempotent. Running `ludus range deploy -t user-defined-roles` a second time reports zero changed tasks.

## Requirements

- Ludus v2.0+
- Templates built: `win2022-server-x64-template`, `win11-22h2-x64-enterprise-template`, `debian-12-x64-server-template`, `kali-x64-desktop-template`
- Collections: `ansible.windows`, `community.windows`, `microsoft.ad` (installed by default on Ludus)
- Roles: `badsectorlabs.ludus_windows_utils`, `badsectorlabs.ludus_elastic_container`, `badsectorlabs.ludus_elastic_agent`
