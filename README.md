# Ludus Source - Bad Sector Labs

A [Ludus source](https://docs.ludus.cloud/docs/using-ludus/sources) shipping production-ready blueprints for offensive security labs. Add the source once, then apply any blueprint to spin up a fully configured range in one step.

```bash
ludus source add https://github.com/badsectorlabs/ludus-source-bsl
ludus blueprint list
```

## Blueprints

| Blueprint ID | Name | VMs | Description |
|---|---|---|---|
| [`goad`](./blueprints/goad/) | Game of Active Directory | 6 | Multi-domain, multi-forest AD attack lab with ADCS ESC1-16, MSSQL, LAPS, gMSA, and the full upstream GOAD ACL chain |
| [`sccm`](./blueprints/sccm/) | SCCM / MECM Hierarchy Lab | 13 | Full CAS + Primary Site + Secondary Site hierarchy; vulnerable to nearly all Misconfiguration Manager techniques |
| [`ad-elastic-range`](./blueprints/ad-elastic-range/) | AD + Elastic Security Range | 6 | Star Wars-themed two-domain AD lab with ADCS ESC1/ESC8, cross-domain MSSQL, and Elastic Agent + Sysmon on every VM |

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

## Source Layout

```
blueprints/
├── goad/                  Game of Active Directory
│   ├── blueprint.yml
│   ├── range-config.yml
│   ├── requirements.yml
│   ├── subscription_refs.yml
│   ├── roles/
│   ├── templates/
│   ├── testing/           validate_goad.py + pytest suite
│   └── README.md
├── sccm/                  SCCM / MECM Hierarchy Lab
│   ├── blueprint.yml
│   ├── range-config.yml
│   ├── requirements.yml
│   ├── subscription_refs.yml
│   ├── roles/
│   ├── templates/
│   └── README.md
└── ad-elastic-range/      AD + Elastic Security Range
    ├── blueprint.yml
    ├── range-config.yml
    ├── requirements.yml
    ├── subscription_refs.yml
    ├── roles/
    ├── templates/
    └── README.md

roles/                     Ansible roles shared across all blueprints (none)
templates/                 Packer templates shared across all blueprints (none)
source.yml                 Source metadata
scripts/validate.py        Manifest validation (run by CI)
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
- [ludus_sccm](https://github.com/Mayyhem/ludus_sccm) by [@Mayyhem](https://github.com/Mayyhem), [@Synzack](https://github.com/Synzack) & [@kernel-sanders](https://github.com/kernel-sanders)
- [Ludus](https://ludus.cloud) by [Bad Sector Labs](https://github.com/badsectorlabs)
