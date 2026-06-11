# Ludus Source - Bad Sector Labs

Ludus blueprints, Packer templates, and Ansible roles & collections for offensive security labs. Add the source; install the resources; then apply them to your range configurations and deployments.

## Quick Start

```bash
# Add this source to your Ludus server via an interactive installer
ludus source add https://github.com/badsectorlabs/ludus-source-bsl

# Or, script the install of source resources
ludus source add https://github.com/badsectorlabs/ludus-source-bsl --all

# Build source templates for your ranges
ludus templates build

# Choose a blueprint to deploy
ludus blueprint apply badsectorlabs-ludus-source-bsl/goad

# Watch Ludus work
ludus range deploy
ludus range logs -f
```

## Blueprints

| Blueprint ID | Name | VMs | Description |
|---|---|---|---|
| [`goad`](./blueprints/goad/) | Game of Active Directory | 6 | Multi-domain, multi-forest AD attack lab with ADCS ESC1-16, MSSQL, LAPS, gMSA, and the full upstream GOAD ACL chain |
| [`ad-elastic-range`](./blueprints/ad-elastic-range/) | AD + Elastic Security Range | 6 | Star Wars-themed two-domain AD lab with ADCS ESC1/ESC8, cross-domain MSSQL, and Elastic Agent + Sysmon on every VM |
| [`ad-elastic-range-clean`](./blueprints/ad-elastic-range-clean/) | Clean AD + Elastic Baseline | 5 | Hardened, vulnerability-free AD baseline (corp.local + sub.corp.local) with Elastic Agent + Sysmon on every Windows VM — a clean baseline for detection engineering and training |

## Templates

This source also ships 21 [Packer](https://www.packer.io/) templates — Debian, Ubuntu, Rocky Linux, Windows client/server, and analyst VMs (Commando VM, FLARE-VM, REMnux). Once installed, they appear in `ludus templates list`. Build one with:

```bash
ludus templates build -n debian-13-x64-server-template
```

See [`templates/README.md`](./templates/README.md) for the full list. `commando-vm`, `flare-vm`, and `remnux` build on a base image and need their companion roles installed first.

## Ansible content

This source vendors Bad Sector Labs' public Ansible roles and collections as **git submodules** pinned to release tags under [`ansible/`](./ansible/). Adding the source installs them automatically and re-syncing refreshes them to the pinned versions. See [`ansible/README.md`](./ansible/README.md) for the full list and what each provides.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on adding new blueprints, and the [source layout](./CONTRIBUTING.md#source-layout) for how the repo is organized.

## License

AGPL-3.0-or-later — See [LICENSE](./LICENSE)

## Acknowledgments

- [GOAD](https://github.com/Orange-Cyberdefense/GOAD) by [@Mayfly277](https://github.com/Mayfly277) / [Orange Cyberdefense](https://github.com/Orange-Cyberdefense)
- [DreadGOAD](https://github.com/dreadnode/DreadGOAD) by [Dreadnode](https://github.com/dreadnode)
