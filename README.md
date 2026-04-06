# Ludus Range Configs

Community-contributed range configurations for [Ludus](https://ludus.cloud) cyber ranges. Each folder contains a complete, tested range config ready to deploy.

## Available Ranges

| Range | Description | VMs | Domains | Templates Required |
|---|---|---|---|---|
| [GOAD](./GOAD/) | Game of Active Directory — multi-forest AD attack lab | 6 + Kali | `sevenkingdoms.local`, `north.sevenkingdoms.local`, `essos.local` | `win2022-server-x64-template`, `kali-x64-desktop-template` |
| [SCCM](./SCCM/) | SCCM/MECM hierarchy lab — CAS + primary + secondary sites with all site system roles | 13 | `mayyhem.com` | `win2022-server-x64-template`, `win11-22h2-x64-enterprise-template` |

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/badsectorlabs/ludus-range-configs.git

# 2. Pick a range config
cd ludus-range-configs/GOAD

# 3. Set the config on your Ludus range
ludus range config set -f range.yml -r <YOUR_RANGE_ID>

# 4. Deploy
ludus range deploy -r <YOUR_RANGE_ID>

# 5. Monitor
ludus range logs -r <YOUR_RANGE_ID> -f
```

## Repository Structure

```
ludus-range-configs/
├── README.md              # This file
├── CONTRIBUTING.md         # How to contribute a range config
├── LICENSE
├── GOAD/
│   ├── README.md          # Range overview, diagram, attack paths, credentials
│   └── range.yml          # The Ludus range config file
├── SCCM/
│   ├── README.md          # SCCM hierarchy overview, diagram, attack paths
│   └── range.yml          # The Ludus range config file
├── <your-range>/
│   ├── README.md
│   └── range.yml
└── ...
```

Each range folder **must** contain:
- `range.yml` — A valid Ludus range config using `{{ range_id }}` and `{{ range_second_octet }}` for portability
- `README.md` — Documentation including a **Mermaid network diagram**, VM table, required roles/collections, credentials, and attack path summary

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full guide. The short version:

1. **Fork** this repo
2. **Create a folder** for your range (e.g., `my-cool-lab/`)
3. Add a `range.yml` and `README.md` (use the [template](./CONTRIBUTING.md#range-readme-template))
4. Include a **Mermaid diagram** in your README showing the network topology
5. **Test your config** on a real Ludus deployment — only submit configs that deploy successfully
6. Open a **Pull Request**

## Requirements

- [Ludus](https://ludus.cloud) v2.0+
- Required templates must be built before deploying (check each range's README for specifics)
- Some ranges require community Ansible roles — install instructions are in each range's README

## License

GPL-3.0-or-later — See [LICENSE](./LICENSE)

## Acknowledgments

- [Ludus](https://ludus.cloud) by [Bad Sector Labs](https://github.com/badsectorlabs)
- [GOAD](https://github.com/Orange-Cyberdefense/GOAD) by [@Mayfly277](https://github.com/Mayfly277) / [Orange Cyberdefense](https://github.com/Orange-Cyberdefense)
- [@ChoiSG](https://github.com/ChoiSG) for early [Ludus community roles](https://github.com/ChoiSG/ludus_ansible_roles)
- [ludus_sccm](https://github.com/Mayyhem/ludus_sccm) by [@Mayyhem](https://github.com/Mayyhem), building on [@Synzack](https://github.com/Synzack) & [@kernel-sanders](https://github.com/kernel-sanders)
