# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) Bad Sector Labs — https://github.com/badsectorlabs/ludus-range-configs
"""
GOAD Post-Deploy Idempotency Verifier
======================================
This script is NOT required for a correct deployment.

All GOAD configuration (ACLs, group memberships, delegations) is handled by the
Ansible roles in ludus_windows_utils (v1.1.34+):

  - ludus_ad_acls        — all AD ACL attack paths; triggers SDPROP and waits
  - ludus_ad_forest_trust — cross-domain FSP group memberships (AcrossTheNarrowSea,
                            DragonsFriends, Spys) with explicit cross-forest credentials
                            and ADWS readiness wait after trust reboot
  - ludus_ad_misconfigs  — CASTELBLACK$ kerb-only constrained delegation
  - ludus_ad_acls (GOAD) — re-applies CASTELBLACK$ delegation post-domain-join
                            (depends_on SRV02 ludus_child_domain_join)

WHY THIS SCRIPT EXISTS
----------------------
Two timing races cannot be fully eliminated in Ansible:

1. SDPROP race (Fixes 1 & 2): Windows SDPROP runs every 60 minutes and resets
   ACLs on adminCount=1 objects (Domain Admins members, Domain Admins group itself)
   back to the AdminSDHolder template. ludus_ad_acls writes the ACEs on AdminSDHolder
   and then triggers SDPROP, waiting for propagation. If a second SDPROP cycle fires
   during the wait (longer deploys), the ACEs may be reset again.

   ludus_ad_acls v1.1.34+ waits for the whenChanged timestamp on Domain Admins to
   confirm propagation, reducing this window significantly. But it cannot prevent
   SDPROP from firing again between propagation and validation.

2. CASTELBLACK$ race (Fix 3): SRV02's domain join recreates the CASTELBLACK$ computer
   object, wiping DC02's delegation. ludus_ad_acls on DC02 now re-applies this AFTER
   the depends_on SRV02 ludus_child_domain_join, eliminating this race entirely.

WHEN TO RUN THIS SCRIPT
-----------------------
Only run this if validate_goad.py reports failures on:
  - acl_varys_GenericAll_AdminSDHolder
  - acl_chain_essos_gmsaDragon_GenericAll_drogon
  - winterfell_castelblack_constrained_delegation
  - adcs_dc03_esc4_khal_drogo_genericall

In that case, re-running the specific role with:
  ludus range deploy -t user-defined-roles --limit <VM> --only-roles <role>
is preferred over this script, since it tests the role itself.

Usage (if needed):
    python3 post_deploy_fix.py --second-octet 1
    python3 post_deploy_fix.py --range-id GOAD1
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from validate_goad import GOADConfig, detect_second_octet

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"
BOLD  = "\033[1m"
YELLOW = "\033[93m"


def run_playbook(playbook_content: str, inventory: str) -> tuple[bool, str]:
    """Run an Ansible playbook inline and return (success, output)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(playbook_content)
        pb_path = f.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(inventory)
        inv_path = f.name
    try:
        result = subprocess.run(
            ["ansible-playbook", pb_path, "-i", inv_path, "-v"],
            capture_output=True, text=True, timeout=180
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Playbook timed out"
    finally:
        os.unlink(pb_path)
        os.unlink(inv_path)


def fix_sdprop_acls(cfg: GOADConfig) -> bool:
    """Re-trigger SDPROP on both domains and wait for propagation.

    This handles the case where SDPROP fired a second time during deployment,
    resetting adminCount=1 object ACLs before validation could run.

    In v1.1.34+, ludus_ad_acls already does this with a propagation wait.
    This function is a fallback for the rare case where it raced again.
    """
    # Re-run ludus_ad_acls on DC01 and DC03 via Ludus directly is preferred,
    # but this inline approach works for quick re-application.
    playbook = f"""---
- hosts: dc01
  gather_facts: false
  tasks:
    - name: Re-trigger SDPROP on sevenkingdoms.local and verify propagation
      ansible.windows.win_powershell:
        script: |
          Import-Module ActiveDirectory
          $domain = Get-ADDomain
          $obj = [ADSI]"LDAP://$($domain.DistinguishedName)"
          $obj.Put("runProtectAdminGroupsTask", 1)
          $obj.SetInfo()
          $before = (Get-ADGroup 'Domain Admins' -Properties whenChanged).whenChanged
          $timer = [System.Diagnostics.Stopwatch]::StartNew()
          while ($timer.Elapsed.TotalSeconds -lt 120) {{
            Start-Sleep -Seconds 5
            $after = (Get-ADGroup 'Domain Admins' -Properties whenChanged -EA SilentlyContinue).whenChanged
            if ($after -gt $before) {{
              Write-Output "OK: SDPROP propagated on sevenkingdoms.local after $([int]$timer.Elapsed.TotalSeconds)s"
              $Ansible.Changed = $false
              return
            }}
          }}
          Write-Output "WARNING: SDPROP propagation not confirmed within 120s"
          $Ansible.Changed = $false
      vars:
        ansible_become: true
        ansible_become_method: runas
        ansible_become_user: 'SEVENKINGDOMS\\\\domainadmin'
        ansible_become_password: 'password'
        ansible_become_flags: 'logon_type=interactive logon_flags=with_profile'

- hosts: dc03
  gather_facts: false
  tasks:
    - name: Re-trigger SDPROP on essos.local and verify propagation
      ansible.windows.win_powershell:
        script: |
          Import-Module ActiveDirectory
          $domain = Get-ADDomain
          $obj = [ADSI]"LDAP://$($domain.DistinguishedName)"
          $obj.Put("runProtectAdminGroupsTask", 1)
          $obj.SetInfo()
          $before = (Get-ADGroup 'Domain Admins' -Properties whenChanged).whenChanged
          $timer = [System.Diagnostics.Stopwatch]::StartNew()
          while ($timer.Elapsed.TotalSeconds -lt 120) {{
            Start-Sleep -Seconds 5
            $after = (Get-ADGroup 'Domain Admins' -Properties whenChanged -EA SilentlyContinue).whenChanged
            if ($after -gt $before) {{
              Write-Output "OK: SDPROP propagated on essos.local after $([int]$timer.Elapsed.TotalSeconds)s"
              $Ansible.Changed = $false
              return
            }}
          }}
          Write-Output "WARNING: SDPROP propagation not confirmed within 120s"
          $Ansible.Changed = $false
      vars:
        ansible_become: true
        ansible_become_method: runas
        ansible_become_user: 'ESSOS\\\\daenerys.targaryen'
        ansible_become_password: 'BurnThemAll!'
        ansible_become_flags: 'logon_type=interactive logon_flags=with_profile'
"""
    inventory = (
        f"[dc01]\n{cfg.dc01_ip} ansible_user=localuser ansible_password=password "
        "ansible_connection=winrm ansible_winrm_transport=ntlm "
        "ansible_winrm_server_cert_validation=ignore ansible_port=5986 ansible_winrm_scheme=https\n"
        f"[dc03]\n{cfg.dc03_ip} ansible_user=localuser ansible_password=password "
        "ansible_connection=winrm ansible_winrm_transport=ntlm "
        "ansible_winrm_server_cert_validation=ignore ansible_port=5986 ansible_winrm_scheme=https\n"
    )
    ok, out = run_playbook(playbook, inventory)
    return ok


def main():
    parser = argparse.ArgumentParser(
        description=(
            "GOAD post-deploy idempotency verifier. NOT required for normal deploys.\n"
            "Run only if validate_goad.py shows SDPROP or delegation failures after deploy."
        )
    )
    parser.add_argument("--second-octet", type=int, default=None)
    parser.add_argument("--range-id", default="GOAD1")
    args = parser.parse_args()

    octet = args.second_octet
    if octet is None:
        octet = detect_second_octet(args.range_id)
    if octet is None:
        m = re.search(r"(\d+)$", args.range_id)
        octet = int(m.group(1)) if m else 1

    cfg = GOADConfig(second_octet=octet)

    print(f"{BOLD}GOAD Post-Deploy Idempotency Verifier{RESET}")
    print(f"Range: {args.range_id} | Network: 10.{octet}.10.0/24")
    print()
    print(f"{YELLOW}NOTE: In v1.1.34+, all GOAD configuration is handled by the Ansible roles.{RESET}")
    print(f"{YELLOW}This script is a fallback for SDPROP timing races only.{RESET}")
    print()
    print("Re-triggering SDPROP on both domains and waiting for propagation...")
    print()

    ok = fix_sdprop_acls(cfg)
    icon = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  SDPROP re-trigger: [{icon}]")

    print()
    print(f"{'=' * 50}")
    if ok:
        print(f"{GREEN}Done. Now run: python3 validate_goad.py --second-octet {octet}{RESET}")
        return 0
    else:
        print(f"{RED}SDPROP re-trigger failed. Consider re-running:{RESET}")
        print(f"  ludus range deploy -t user-defined-roles --limit <DC> --only-roles ludus_ad_acls")
        return 1


if __name__ == "__main__":
    sys.exit(main())
