# Ludus Source - Bad Sector Labs

A [Ludus source](https://docs.ludus.cloud/docs/using-ludus/sources) shipping production-ready blueprints — and the Packer templates they build on — for offensive security labs. Add the source once, build the templates a blueprint needs, then apply it to spin up a fully configured range.

```bash
ludus source add https://github.com/badsectorlabs/ludus-source-bsl
ludus blueprint list
```

## Blueprints

| Blueprint ID | Name | VMs | Description |
|---|---|---|---|
| [`goad`](./blueprints/goad/) | Game of Active Directory | 6 | Multi-domain, multi-forest AD attack lab with ADCS ESC1-16, MSSQL, LAPS, gMSA, and the full upstream GOAD ACL chain |
| [`ad-elastic-range`](./blueprints/ad-elastic-range/) | AD + Elastic Security Range | 6 | Star Wars-themed two-domain AD lab with ADCS ESC1/ESC8, cross-domain MSSQL, and Elastic Agent + Sysmon on every VM |
| [`ad-elastic-range-clean`](./blueprints/ad-elastic-range-clean/) | Clean AD + Elastic Baseline | 5 | Hardened, vulnerability-free AD baseline (corp.local + sub.corp.local) with Elastic Agent + Sysmon on every Windows VM — a clean baseline for detection engineering and training |

## Quick Start

```bash
# Add this source to your Ludus server
ludus source add https://github.com/badsectorlabs/ludus-source-bsl

# List available blueprints
ludus blueprint list

# Apply a blueprint and deploy
ludus blueprint apply ludus-source-bsl/ad-elastic-range
ludus range deploy

# Follow the logs
ludus range logs -f
```

## Templates

This source also ships the [Packer](https://www.packer.io/) templates the blueprints build on — Debian, Ubuntu, Rocky Linux, Windows client/server, and analyst VMs (Commando VM, FLARE-VM, REMnux). Once the source is added they appear in `ludus templates list`, ready to build:

```bash
ludus templates build -n debian-13-x64-server-template
```

See [`templates/`](./templates/) for the full list. `commando-vm`, `flare-vm`, and `remnux` build on a base image and need their companion roles installed first — see [`templates/README.md`](./templates/README.md).

## Roles

This source vendors Bad Sector Labs' public Ludus roles as **git submodules** under [`ansible/roles/`](./ansible/roles/), each pinned to a release tag. Adding the source installs them automatically — no manual `ansible-galaxy` step — and a re-sync refreshes them to the pinned versions.

| Role | Purpose |
|---|---|
| [`ludus_adcs`](./ansible/roles/ludus_adcs/) | Active Directory Certificate Services with ESC1-16 vulnerable templates |
| [`ludus_mssql`](./ansible/roles/ludus_mssql/) | SQL Server with impersonation and linked-server attack paths |
| [`ludus_elastic_container`](./ansible/roles/ludus_elastic_container/) | Elasticsearch + Kibana + Fleet server |
| [`ludus_elastic_agent`](./ansible/roles/ludus_elastic_agent/) | Elastic Agent + optional Sysmon on endpoints |
| [`ludus_commandovm`](./ansible/roles/ludus_commandovm/) | Mandiant Commando VM offensive Windows toolset |
| [`ludus_flarevm`](./ansible/roles/ludus_flarevm/) | Mandiant FLARE-VM malware-analysis toolset |
| [`ludus_remnux`](./ansible/roles/ludus_remnux/) | REMnux reverse-engineering distribution |
| [`ludus_adaptix_c2`](./ansible/roles/ludus_adaptix_c2/) | Adaptix C2 framework server |
| [`ludus_bloodhound_ce`](./ansible/roles/ludus_bloodhound_ce/) | BloodHound Community Edition |
| [`ludus_emux`](./ansible/roles/ludus_emux/) | EMUX firmware/IoT emulation environment |
| [`ludus_vulhub`](./ansible/roles/ludus_vulhub/) | Vulhub vulnerable-application environments |
| [`ludus_xz_backdoor`](./ansible/roles/ludus_xz_backdoor/) | CVE-2024-3094 (xz-utils) backdoor lab |

## Collections

This source also vendors the [`ludus_windows_utils`](./ansible/collections/ludus_windows_utils/) Ansible collection as a git submodule under [`ansible/collections/`](./ansible/collections/), pinned to a release tag. It provides the Windows utility roles (AD password policy, bulk content, etc.) the blueprints rely on, and installs automatically when the source is added.

> Each entry under `ansible/roles/` and `ansible/collections/` is a git **submodule** with an **absolute upstream** URL (`https://github.com/badsectorlabs/<repo>.git`), pinned to a release tag. Clone or sync the source with submodule support (Ludus does this automatically) to materialize them; for a manual clone use `git clone --recurse-submodules`.

## Source Layout

```
blueprints/
├── goad/                    Game of Active Directory (+ testing/ pytest suite)
├── ad-elastic-range/        AD + Elastic Security Range
└── ad-elastic-range-clean/  Clean AD + Elastic Baseline
                             each: blueprint.yml, range-config.yml, requirements.yml, README.md
templates/                   Packer templates (Debian, Ubuntu, Rocky, Windows, analyst VMs)
ansible/
├── roles/                   Vendored ludus_* roles (git submodules, pinned to tags)
└── collections/             Vendored collections — ludus_windows_utils (git submodule)
source.yml                   Source metadata
scripts/validate.py          Manifest validation (run by CI)
.gitmodules                  Submodule definitions (absolute upstream URLs)
```

## Requirements

- [Ludus](https://ludus.cloud) v2.0+
- Templates must be built before deploying — see each blueprint's README for specifics

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on adding new blueprints.

## License

AGPL-3.0-or-later — See [LICENSE](./LICENSE)

## Acknowledgments

- [GOAD](https://github.com/Orange-Cyberdefense/GOAD) by [@Mayfly277](https://github.com/Mayfly277) / [Orange Cyberdefense](https://github.com/Orange-Cyberdefense)
- [DreadGOAD](https://github.com/dreadnode/DreadGOAD) by [Dreadnode](https://github.com/dreadnode)
- [Ludus](https://ludus.cloud) by [Bad Sector Labs](https://github.com/badsectorlabs)
