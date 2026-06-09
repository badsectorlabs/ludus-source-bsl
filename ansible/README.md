# Ludus Ansible Content

The Ansible roles and collections shipped by the
[Bad Sector Labs Ludus source](https://github.com/badsectorlabs/ludus-source-bsl).

## Roles

Vendored under [`roles/`](./roles/); each links to its upstream repository.

| Role | Purpose |
|---|---|
| [`ludus_adcs`](https://github.com/badsectorlabs/ludus_adcs) | Active Directory Certificate Services with ESC1-16 vulnerable templates |
| [`ludus_mssql`](https://github.com/badsectorlabs/ludus_mssql) | SQL Server with impersonation and linked-server attack paths |
| [`ludus_elastic_container`](https://github.com/badsectorlabs/ludus_elastic_container) | Elasticsearch + Kibana + Fleet server |
| [`ludus_elastic_agent`](https://github.com/badsectorlabs/ludus_elastic_agent) | Elastic Agent + optional Sysmon on endpoints |
| [`ludus_commandovm`](https://github.com/badsectorlabs/ludus_commandovm) | Mandiant Commando VM offensive Windows toolset |
| [`ludus_flarevm`](https://github.com/badsectorlabs/ludus_flarevm) | Mandiant FLARE-VM malware-analysis toolset |
| [`ludus_remnux`](https://github.com/badsectorlabs/ludus_remnux) | REMnux reverse-engineering distribution |
| [`ludus_adaptix_c2`](https://github.com/badsectorlabs/ludus_adaptix_c2) | Adaptix C2 framework server |
| [`ludus_bloodhound_ce`](https://github.com/badsectorlabs/ludus_bloodhound_ce) | BloodHound Community Edition |
| [`ludus_emux`](https://github.com/badsectorlabs/ludus_emux) | EMUX firmware/IoT emulation environment |
| [`ludus_vulhub`](https://github.com/badsectorlabs/ludus_vulhub) | Vulhub vulnerable-application environments |
| [`ludus_xz_backdoor`](https://github.com/badsectorlabs/ludus_xz_backdoor) | CVE-2024-3094 (xz-utils) backdoor lab |

## Collections

Vendored under [`collections/`](./collections/):

| Collection | Purpose |
|---|---|
| [`ludus_windows_utils`](https://github.com/badsectorlabs/ludus_windows_utils) | Windows utility roles (AD password policy, bulk content, LAPS, gMSA, etc.) the blueprints rely on |

## Submodules

Each entry under `roles/` and `collections/` is a git **submodule** with an
**absolute upstream** URL (`https://github.com/badsectorlabs/<repo>.git`), pinned
to a release tag. Ludus materializes them automatically when the source is added
or synced; for a manual clone use:

```bash
git clone --recurse-submodules https://github.com/badsectorlabs/ludus-source-bsl
```

Submodule pins are kept current by an automated workflow — see
[`.github/workflows/README.md`](../.github/workflows/README.md).
