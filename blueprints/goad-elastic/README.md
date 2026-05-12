# GOAD + Elastic Security Blueprint

A Ludus blueprint that combines an Active Directory attack lab with a full [Elastic Security](https://www.elastic.co/security) stack for detection and response training.

## What This Deploys

| VM | Template | VLAN | IP | Purpose |
|----|----------|------|----|---------|
| `elastic` | debian-12-x64-server-template | 20 | .20.2 | Elastic container (SIEM + Fleet) |
| `DC01` | win2022-server-x64-template | 10 | .10.10 | Primary DC — corp.local |
| `SRV01` | win2022-server-x64-template | 10 | .10.11 | Member server — IIS/WebDAV/SMB |
| `WS01` | win11-22h2-x64-enterprise-template | 10 | .10.20 | Domain workstation (Win11) |
| `kali` | kali-x64-desktop-template | 99 | .99.1 | Attacker |

**Estimated deploy time:** 45–60 minutes  
**RAM required:** ~28 GB

## Roles Used

### `badsectorlabs.ludus_windows_utils` (collection)

Every role in the collection is exercised:

| Role | VM(s) | What it configures |
|------|-------|--------------------|
| `ludus_ad_password_policy` | DC01 | Weak policy — min length 4, no complexity |
| `ludus_bulk_ad_content` | DC01 | IT/HR OUs, groups, users, service accounts |
| `ludus_ad_gmsa` | DC01 (create), SRV01 (install) | `gmsaWeb$` with HTTP SPNs on SRV01 |
| `ludus_ad_laps` | DC01 (DC-side), SRV01 (client) | LAPS schema + GPO + IT-Admins reader |
| `ludus_ad_misconfigs` | DC01, SRV01, WS01 | SMB signing off, WebClient, Print Spooler |
| `ludus_ad_anonymous_rpc` | DC01 | Anonymous SAMR/LSA enumeration |
| `ludus_ad_acls` | DC01 | ACE attack paths (see Attack Paths below) |
| `ludus_smb_shares` | DC01, SRV01 | Named shares with permissions |
| `ludus_files` | DC01, SRV01, WS01 | Credential breadcrumbs + honeypot docs |
| `ludus_iis_webdav` | SRV01 | IIS + WebDAV + WebClient service |
| `ludus_child_domain_join` | SRV01, WS01 | Domain join to corp.local |

### `badsectorlabs.ludus_elastic_container`

Runs the [Elastic Container Project](https://github.com/peasead/elastic-container) on `elastic` (Debian 12). Deploys Elasticsearch, Kibana, and Fleet Server. Creates an agent policy with Elastic Defend and Windows integrations pre-configured.

### `badsectorlabs.ludus_elastic_agent`

Deploys the Elastic Agent to DC01, SRV01, and WS01. The `ludus_elastic_install_sysmon: true` flag installs Sysmon alongside the agent on each Windows VM. Agent enrollment token and Fleet server URL are automatically read from the elastic container output — no manual wiring required.

## Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Kibana | `https://10.X.20.2:5601` | `elastic` / `ElasticR0cks!` |
| Fleet Server | `https://10.X.20.2:8220` | — |
| DC01 (RDP) | `10.X.10.10:3389` | `CORP\domainadmin` / `password` |
| SRV01 (RDP) | `10.X.10.11:3389` | `CORP\domainadmin` / `password` |
| WS01 (RDP) | `10.X.10.20:3389` | `CORP\domainadmin` / `password` |
| Kali | `10.X.99.1` | `kali` / `kali` |

Replace `X` with your range's second octet (visible in `ludus range list`).

## Lab Users

| Username | Password | Groups | Notes |
|----------|----------|--------|-------|
| `alice.smith` | `Password1` | Domain Admins, IT-Admins | High-value target |
| `bob.jones` | `Summer2024` | HelpDesk | ForceChangePassword over carol.white |
| `carol.white` | `Welcome1` | HR-Staff | |
| `svc.sql` | `Serv1ceP@ss!` | SQLAdmins | GenericAll on IT-Admins |
| `svc.backup` | `B@ckupP@ss1` | — | AS-REP roastable (no pre-auth) |

## Attack Paths

```
AS-REP Roasting
  └─ svc.backup (no Kerberos pre-auth) → hash → crack → Password

ACL Chain
  └─ svc.sql --[GenericAll]--> IT-Admins
       └─ Add self to IT-Admins → alice.smith creds → DA

ForceChangePassword
  └─ bob.jones --[ForceChangePassword]--> carol.white

Kerberoasting
  └─ gmsaWeb$ has HTTP SPNs → TGS → crack

NTLM Coercion
  └─ SRV01: WebClient + IIS WebDAV enabled
       └─ PetitPotam / PrinterBug → relay to LDAP or SMB

LAPS
  └─ IT-Admins + alice.smith can read local admin password for SRV01

Credential Breadcrumbs
  └─ C:\Shares\IT-Tools\install.bat — plaintext alice.smith creds
  └─ C:\Users\Public\Documents\VPN-Config.txt — carol.white creds
  └─ C:\Users\Public\Desktop\credentials.txt — multiple creds
```

## Deploy Instructions

### 1. Install required roles and collections

```bash
ludus ansible collection add badsectorlabs.ludus_windows_utils
ludus ansible roles add badsectorlabs.ludus_elastic_container
ludus ansible roles add badsectorlabs.ludus_elastic_agent
```

### 2. Apply the blueprint

```bash
ludus blueprint apply <source>/goad-elastic
ludus range deploy
```

Or use the range config directly:

```bash
ludus range config set -f blueprints/goad-elastic/range-config.yml
ludus range deploy
```

### 3. Monitor progress

```bash
ludus range logs -f       # follow logs live
ludus range errors        # show only fatal errors
```

### 4. Validate

After deploy, verify agents are enrolled in Kibana:
- Navigate to `https://10.X.20.2:5601`
- Go to Fleet → Agents — three Windows agents should show as Healthy

## Development / Role Iteration

Use the tight inner loop when iterating on individual roles:

```bash
# Push an updated role
ludus ansible role add -d ./path/to/role --force

# Test only that role on one VM
ludus range deploy -t user-defined-roles \
  --limit AR-DC01 \
  --only-roles badsectorlabs.ludus_windows_utils.ludus_ad_misconfigs

# Check for errors
ludus range errors

# Verify idempotency — run again, must show 0 changed
ludus range deploy -t user-defined-roles \
  --limit AR-DC01 \
  --only-roles badsectorlabs.ludus_windows_utils.ludus_ad_misconfigs
```

## Idempotency

This blueprint is fully idempotent. Running `ludus range deploy -t user-defined-roles` a second time reports zero changed tasks.

## Requirements

- Ludus v2.0+
- Templates built: `win2022-server-x64-template`, `win11-22h2-x64-enterprise-template`, `debian-12-x64-server-template`, `kali-x64-desktop-template`
- Ansible collections on the Ludus server: `ansible.windows`, `community.windows`, `microsoft.ad` (installed by default)
- Roles: `badsectorlabs.ludus_windows_utils`, `badsectorlabs.ludus_elastic_container`, `badsectorlabs.ludus_elastic_agent`
