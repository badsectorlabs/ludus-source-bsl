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

## Source Layout

```
blueprints/
├── goad/                    Game of Active Directory (+ testing/ pytest suite)
├── ad-elastic-range/        AD + Elastic Security Range
└── ad-elastic-range-clean/  Clean AD + Elastic Baseline
                             each: blueprint.yml, range-config.yml, requirements.yml, README.md
templates/                   Packer templates (Debian, Ubuntu, Rocky, Windows, analyst VMs)
source.yml                   Source metadata
scripts/validate.py          Manifest validation (run by CI)
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
