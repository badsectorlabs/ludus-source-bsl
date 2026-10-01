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
| `debian-11-x64-server-template` | Debian 11 (Bullseye) minimal x64 server. |
| `rocky-8-x64-server-template` | Rocky Linux 8 minimal x64 server. |
| `rocky-9-x64-server-template` | Rocky Linux 9 minimal x64 server. |
| `ubuntu-20.04-x64-server-template` | Ubuntu 20.04 LTS (Focal Fossa) x64 server. |
| `ubuntu-22.04-x64-server-template` | Ubuntu 22.04 LTS (Jammy Jellyfish) x64 server. |
| `ubuntu-24.04-x64-server-template` | Ubuntu 24.04 LTS (Noble Numbat) x64 server. |
| `ubuntu-24.04-x64-desktop-template` | Ubuntu 24.04 LTS (Noble Numbat) x64 desktop. |

#### Debian 10 Python runtime

The Debian 10 template bootstraps Python 3.11.16 before running its Ansible
provisioner. It installs a pinned
[Python standalone distribution](https://github.com/astral-sh/python-build-standalone/releases/tag/20260924)
under `/opt/ludus/python3.11`, verifies the archive's SHA-256 checksum, and exposes
`/usr/local/bin/python3.11` for Ansible provisioning and interpreter discovery.
Debian's `/usr/bin/python3` remains unchanged for system packages.

The bootstrap also builds checksum-pinned `python-apt` 1.8.4.3 for that interpreter
against Buster's native APT libraries, including the Python 3.10+ size-type
compatibility fix. It installs `apt`, `apt_pkg`, and `apt_inst`; Debian's
`python3-apt` package alone only supplies bindings for system Python 3.7.
Build prerequisites are `ca-certificates`, `curl`, `g++`, `libapt-pkg-dev`,
`patch`, and `xz-utils`. The compiled extensions continue to use Debian's native
APT shared libraries; they are not a portable, statically linked APT bundle.

The build needs Debian's archive repositories and GitHub release assets.
Python version, release tag, archive checksum, and the APT source version/checksum
are pinned in `debian10/scripts/bootstrap-python.sh`. Refresh related pins
together. A Python minor-version change also requires updating the installation
path and `ansible_python_interpreter` in `debian10/debian10.pkr.hcl`.
The Ansible provisioner installs the hostname prerequisites through `apt`, so a
build verifies package operations as well as fact gathering.

#### Debian 11 Python runtime

The Debian 11 template is adapted from
[Ludus 2.2.4](https://gitlab.com/badsectorlabs/ludus/-/tree/2.2.4/ludus-server/packer/debian11?ref_type=tags),
with its Debian 11.7.0 installer and preseed configuration. Debian 11 ships
[Python 3.9.2](https://packages.debian.org/bullseye/python3).
[Ansible-core 2.21 supports Python 3.9–3.14 on managed nodes](https://docs.ansible.com/projects/ansible/devel/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix),
so this template uses `/usr/bin/python3` without a standalone Python bootstrap.
The Ansible controller separately requires Python 3.12–3.14.

#### Ubuntu 20.04 Python runtime

Ubuntu 20.04's system Python 3.8 is below core 2.21's managed-node minimum.
`ubuntu-20.04-x64-server/scripts/bootstrap-python.sh` installs the same private
Python 3.11.16 distribution and builds checksum-pinned `python-apt` 2.2.1 against
Focal's native APT libraries before either Ansible provisioner runs. System
Python and APT remain unchanged. The build needs `ca-certificates`, `curl`,
`g++`, `libapt-pkg-dev`, and `xz-utils`, plus access to the Ubuntu repositories,
the pinned Debian source archive, and GitHub release assets.

#### Rocky 8 Python runtime

Rocky 8's platform Python 3.6 is also below core 2.21's managed-node minimum.
`rocky-8-x64-server/bootstrap-python.sh` installs the same private Python 3.11.16
distribution without replacing platform Python, system DNF/RPM, or their shared
libraries. `build-bindings.py` installs `dnf`, `hawkey`, `libdnf`, `libcomps`,
`rpm`, `gpg`, and `selinux` for the private interpreter. Native extensions are
built from Rocky's checksum-pinned source RPMs, including the vendor patches,
and linked against the installed Rocky libraries.

The build uses BaseOS/AppStream packages, PowerTools development headers,
checksum-pinned SWIG 4.2.1, and the Rocky source-RPM and GitHub release servers.
Compilers, development headers, and RPM build tools are installed by the
bootstrap. It checks that each installed runtime package matches its source-RPM
pin; a new Rocky erratum requires refreshing the corresponding source version
and checksum, not bypassing that check. Runtime probes verify RPM database
access, DNF repository/release detection, SELinux calls, and the unchanged system
Python before publishing `/usr/local/bin/python3.11` for discovery.

Python 3.11 is intentional: these EL8 vendor builds still use `distutils`, which
Python 3.12 removed. A Python minor-version upgrade requires adapting and
retesting the binding builds, not just changing the interpreter archive.

#### Rebuilding and retained guests

Updating Ludus or syncing this source does not modify already-built templates
or existing VMs. Rebuild templates to pick up the bootstrap changes. For retained
guests, transfer and run the corresponding bootstrap over SSH before using
Ansible; Ansible's `raw` module can run shell commands without guest Python, but
`copy` and fact gathering already require a supported interpreter.
For Rocky 8, also transfer `build-bindings.py` to
`/var/tmp/ludus-build-bindings.py` before running its bootstrap.
Use `/usr/local/bin/python3.11` as `ansible_python_interpreter` for repaired
legacy guests. Do not copy extension modules from the distro's older Python
site-packages into the private interpreter.

The standalone Python already contains the standard library; Ludus does not
build a custom static Python. Extra Python libraries depend on the modules a
role uses. For example, `deb822_repository` needs `python-debian`,
`community.crypto` tasks can need `cryptography`, and SELinux policy-management
tasks can need additional policy bindings. Install those for the interpreter
Ansible actually uses. Controller-side filters and connections use the
controller's separate dependencies, not packages in each guest.
These interpreter changes do not extend the guest distribution's security
support; native package-manager libraries still come from that distribution.

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
