# Ludus Templates

Self-contained [Packer](https://www.packer.io/) templates shipped by the
[Bad Sector Labs Ludus source](https://github.com/badsectorlabs/ludus-source-bsl).
Each directory builds one Ludus VM template. See
https://docs.ludus.cloud/docs/templates for details.

## Installing

Add this source to Ludus — its templates appear in the catalog, ready to sync
and build:

```
ludus source add https://github.com/badsectorlabs/ludus-source-bsl.git
```

Then build a template with `ludus templates build -n <template-name>`.

## Available templates

The name in the first column is what you pass to `ludus templates build -n`.

### Windows desktop

| Template | Description |
| --- | --- |
| `win10-22h2-x64-enterprise-template` | Windows 10 22H2 Enterprise (x64). |
| `win11-23h2-x64-enterprise-template` | Windows 11 23H2 Enterprise (x64). |
| `win11-24h2-x64-enterprise-tpm-template` | Windows 11 24H2 Enterprise (x64) with a virtual TPM for Secure Boot. |
| `win11-25h2-x64-enterprise-template` | Windows 11 25H2 Enterprise (x64). |
| `win11-25h2-x64-enterprise-no-defender-template` | Windows 11 25H2 Enterprise (x64) with Windows Defender disabled. |

### Windows server

| Template | Description |
| --- | --- |
| `win2012r2-server-x64-template` | Windows Server 2012 R2 (x64). |
| `win2016-server-x64-template` | Windows Server 2016 (x64). |
| `win2019-server-x64-template` | Windows Server 2019 (x64). |
| `win2019-server-x64-no-security-updates-template` | Windows Server 2019 (x64) built without security updates, for patch-gap and vulnerability labs. |
| `win2025-server-x64-tpm-template` | Windows Server 2025 (x64) with a virtual TPM for Secure Boot. |

### Linux

| Template | Description |
| --- | --- |
| `debian-10-x64-server-template` | Debian 10 (Buster) minimal x64 server. |
| `debian-13-x64-server-template` | Debian 13 (Trixie) minimal x64 server. |
| `rocky-8-x64-server-template` | Rocky Linux 8 minimal x64 server. |
| `rocky-9-x64-server-template` | Rocky Linux 9 minimal x64 server. |
| `ubuntu-20.04-x64-server-template` | Ubuntu 20.04 LTS (Focal Fossa) x64 server. |
| `ubuntu-22.04-x64-server-template` | Ubuntu 22.04 LTS (Jammy Jellyfish) x64 server. |
| `ubuntu-24.04-x64-server-template` | Ubuntu 24.04 LTS (Noble Numbat) x64 server. |
| `ubuntu-24.04-x64-desktop-template` | Ubuntu 24.04 LTS (Noble Numbat) x64 desktop. |

### Security / analyst workstations

These need their companion roles installed as well. Install all three
templates and their roles in one command:

```
ludus source add https://github.com/badsectorlabs/ludus-source-bsl --templates commando-vm-template,flare-vm-template,remnux-template --source-roles ludus_commandovm,ludus_flarevm,ludus_remnux
```

| Template | Description |
| --- | --- |
| `commando-vm-template` | Windows offensive-security workstation preloaded with Mandiant Commando VM (red-team and pentest tooling). |
| `flare-vm-template` | Windows reverse-engineering and malware-analysis workstation built on Mandiant FLARE-VM. |
| `remnux-template` | REMnux Linux toolkit for reverse-engineering and analyzing malicious software. |
