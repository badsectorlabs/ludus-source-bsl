"""
GOAD Pytest Unit Tests
======================
Wraps validate_goad.py checks as individual pytest test cases.
Each test maps to a specific GOAD misconfiguration or attack path.

Run:
    pytest test_goad.py -v                        # All tests
    pytest test_goad.py -v -k "mssql"             # Only MSSQL tests
    pytest test_goad.py -v -k "winterfell"        # Only winterfell tests
    pytest test_goad.py -v --tb=short             # Short tracebacks
    pytest test_goad.py -v --second-octet=1       # Explicit octet
    pytest test_goad.py -v --range-id=GOAD2       # Different range

Configuration (environment variables or conftest.py):
    GOAD_SECOND_OCTET=1     Network second octet
    GOAD_RANGE_ID=GOAD1     Ludus range ID
"""

import os
import re
import sys
import pytest

# Add testing directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))
from validate_goad import (
    GOADConfig, winrm_ps, smb_shares, tcp_reachable,
    run_network_checks, run_smb_checks, run_ad_user_checks,
    run_ad_group_checks, run_acl_checks, run_acl_chain_checks,
    run_misconfiguration_checks, run_sysvol_and_files_checks,
    run_laps_reader_checks, run_ntlm_and_auth_checks,
    run_kerberos_checks, run_mssql_checks, run_mssql_extended_checks,
    run_adcs_checks, run_adcs_template_checks, run_cross_domain_group_checks,
    run_password_policy_checks, run_anonymous_rpc_check, run_forest_trust_checks,
    detect_second_octet,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
# NOTE: pytest_addoption and cfg fixture are defined in conftest.py
# to avoid duplicate registration. Do not redefine them here.


# ── Helper ────────────────────────────────────────────────────────────────────

def assert_results(results, test_name_pattern: str = ""):
    """Assert all CheckResults pass, printing failures."""
    failures = []
    for r in results:
        if r.skipped:
            continue
        if not r.passed:
            if not test_name_pattern or test_name_pattern in r.name:
                failures.append(f"{r.name}: {r.detail}")
    assert not failures, "Failed checks:\n  " + "\n  ".join(failures)


# ── Network Tests ─────────────────────────────────────────────────────────────

class TestNetwork:
    def test_dc01_smb_reachable(self, cfg):
        assert tcp_reachable(cfg.dc01_ip, 445), \
            f"DC01 {cfg.dc01_ip}:445 not reachable"

    def test_dc01_ldap_reachable(self, cfg):
        assert tcp_reachable(cfg.dc01_ip, 389), \
            f"DC01 {cfg.dc01_ip}:389 (LDAP) not reachable"

    def test_dc01_kerberos_reachable(self, cfg):
        assert tcp_reachable(cfg.dc01_ip, 88), \
            f"DC01 {cfg.dc01_ip}:88 (Kerberos) not reachable"

    def test_dc02_smb_reachable(self, cfg):
        assert tcp_reachable(cfg.dc02_ip, 445), \
            f"DC02 {cfg.dc02_ip}:445 not reachable"

    def test_dc02_ldap_reachable(self, cfg):
        assert tcp_reachable(cfg.dc02_ip, 389), \
            f"DC02 {cfg.dc02_ip}:389 not reachable"

    def test_srv02_smb_reachable(self, cfg):
        assert tcp_reachable(cfg.srv02_ip, 445), \
            f"SRV02 {cfg.srv02_ip}:445 not reachable"

    def test_srv02_mssql_reachable(self, cfg):
        assert tcp_reachable(cfg.srv02_ip, 1433), \
            f"SRV02 {cfg.srv02_ip}:1433 (MSSQL) not reachable"

    def test_srv02_iis_reachable(self, cfg):
        assert tcp_reachable(cfg.srv02_ip, 80), \
            f"SRV02 {cfg.srv02_ip}:80 (IIS) not reachable"

    def test_dc03_smb_reachable(self, cfg):
        assert tcp_reachable(cfg.dc03_ip, 445), \
            f"DC03 {cfg.dc03_ip}:445 not reachable"

    def test_srv03_adcs_reachable(self, cfg):
        assert tcp_reachable(cfg.srv03_ip, 443) or \
               tcp_reachable(cfg.srv03_ip, 80), \
            f"SRV03 {cfg.srv03_ip}:80/443 (ADCS) not reachable"

    def test_srv03_mssql_reachable(self, cfg):
        assert tcp_reachable(cfg.srv03_ip, 1433), \
            f"SRV03 {cfg.srv03_ip}:1433 (MSSQL) not reachable"


# ── SMB Tests ─────────────────────────────────────────────────────────────────

class TestSMB:
    def test_smb_signing_disabled_all_hosts(self, cfg):
        results = run_smb_checks(cfg)
        signing = [r for r in results if "signing_disabled" in r.name]
        assert_results(signing)

    def test_castelblack_thewall_share(self, cfg):
        ok, shares = smb_shares(cfg.srv02_ip, cfg)
        assert ok, "smbclient failed on castelblack"
        assert "thewall" in shares, \
            f"'thewall' share missing on castelblack. Found: {shares}"

    def test_castelblack_public_share(self, cfg):
        ok, shares = smb_shares(cfg.srv02_ip, cfg)
        assert ok, "smbclient failed on castelblack"
        assert "public" in shares, \
            f"'public' share missing on castelblack. Found: {shares}"

    def test_castelblack_all_share(self, cfg):
        ok, shares = smb_shares(cfg.srv02_ip, cfg)
        assert ok, "smbclient failed on castelblack"
        assert "all" in shares, \
            f"'all' share missing on castelblack. Found: {shares}"

    def test_braavos_public_share(self, cfg):
        ok, shares = smb_shares(cfg.srv03_ip, cfg)
        assert ok, "smbclient failed on braavos"
        assert "public" in shares, \
            f"'public' share missing on braavos. Found: {shares}"

    def test_braavos_certenroll_share(self, cfg):
        ok, shares = smb_shares(cfg.srv03_ip, cfg)
        assert ok, "smbclient failed on braavos"
        assert "CertEnroll" in shares, \
            f"'CertEnroll' share missing on braavos. Found: {shares}"


# ── AD User Tests ─────────────────────────────────────────────────────────────

class TestADUsers:
    @pytest.mark.parametrize("username", [
        "arya.stark", "eddard.stark", "catelyn.stark", "robb.stark",
        "sansa.stark", "brandon.stark", "rickon.stark", "hodor",
        "jon.snow", "samwell.tarly", "jeor.mormont", "sql_svc",
    ])
    def test_north_user_exists(self, cfg, username):
        ok, out = winrm_ps(cfg.dc02_ip, f"""
Import-Module ActiveDirectory
$u = Get-ADUser {username} -ErrorAction SilentlyContinue
Write-Output $(if ($u) {{ 'EXISTS' }} else {{ 'MISSING' }})
""", cfg)
        assert ok and "EXISTS" in out, \
            f"User '{username}' missing in north.sevenkingdoms.local"

    def test_samwell_password_in_description(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$u = Get-ADUser samwell.tarly -Properties Description
Write-Output $u.Description
""", cfg)
        assert ok and "Heartsbane" in out, \
            f"samwell.tarly description should contain 'Heartsbane', got: {out}"

    @pytest.mark.parametrize("username", [
        "daenerys.targaryen", "viserys.targaryen", "khal.drogo",
        "jorah.mormont", "missandei", "drogon", "sql_svc",
    ])
    def test_essos_user_exists(self, cfg, username):
        ok, out = winrm_ps(cfg.dc03_ip, f"""
Import-Module ActiveDirectory
$u = Get-ADUser {username} -ErrorAction SilentlyContinue
Write-Output $(if ($u) {{ 'EXISTS' }} else {{ 'MISSING' }})
""", cfg)
        assert ok and "EXISTS" in out, \
            f"User '{username}' missing in essos.local"


# ── AD Group Tests ────────────────────────────────────────────────────────────

class TestADGroups:
    def test_stark_group_has_arya(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$m = Get-ADGroupMember Stark | Select-Object -ExpandProperty SamAccountName
Write-Output ($m -join ',')
""", cfg)
        assert ok and "arya.stark" in out.lower(), \
            f"arya.stark not in Stark group. Members: {out}"

    def test_nightwatch_has_jon_snow(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$m = Get-ADGroupMember 'Night Watch' | Select-Object -ExpandProperty SamAccountName
Write-Output ($m -join ',')
""", cfg)
        assert ok and "jon.snow" in out.lower(), \
            f"jon.snow not in Night Watch. Members: {out}"

    def test_drogon_effective_domain_admin_via_nesting(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$da = Get-ADGroupMember 'Domain Admins' -Recursive |
      Where-Object { $_.SamAccountName -eq 'drogon' }
Write-Output $(if ($da) { 'YES' } else { 'NO' })
""", cfg)
        assert ok and "YES" in out, \
            "drogon is NOT an effective Domain Admin via nesting (Dragons→QueenProtector→DA)"

    def test_across_the_narrow_sea_has_member(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup AcrossTheNarrowSea -Properties Members
Write-Output "Count:$($grp.Members.Count)"
""", cfg)
        # Members are ForeignSecurityPrincipals - check via Members property count
        assert ok and "Count:0" not in out and out.strip() != "Count:", \
            "AcrossTheNarrowSea group has no members (daenerys.targaryen should be a ForeignSecurityPrincipal)"

    def test_dragons_friends_has_members(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup DragonsFriends -Properties Members
Write-Output "Count:$($grp.Members.Count)"
""", cfg)
        assert ok and "Count:0" not in out, \
            "DragonsFriends group has no members"

    def test_spys_has_members(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup Spys -Properties Members
Write-Output "Count:$($grp.Members.Count)"
""", cfg)
        # Spys contains Small Council as ForeignSecurityPrincipal (cross-forest)
        # Get-ADGroup -Properties Members returns DN list
        assert ok and "Count:0" not in out, \
            f"Spys group has no members (Small Council FSP should be present): {out}"


# ── Misconfiguration Tests ────────────────────────────────────────────────────

class TestWinterfellMisconfigs:
    def test_firewall_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip,
            "Write-Output (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count",
            cfg)
        assert ok and out.strip() == "0", f"Firewall still enabled: {out}"

    def test_smb_signing_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip,
            "Write-Output (Get-SmbServerConfiguration).RequireSecuritySignature",
            cfg)
        assert ok and "False" in out, f"SMB signing not disabled: {out}"

    def test_print_spooler_running(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip,
            "Write-Output (Get-Service Spooler).Status", cfg)
        assert ok and "Running" in out, f"Print Spooler not running: {out}"

    def test_webclient_running(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip,
            "Write-Output (Get-Service WebClient -ErrorAction SilentlyContinue).Status",
            cfg)
        assert ok and "Running" in out, f"WebClient not running: {out}"

    def test_autologon_robb_stark(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$al = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Write-Output $al.DefaultUserName
""", cfg)
        assert ok and "robb.stark" in out.lower(), \
            f"Autologon not set to robb.stark: {out}"

    def test_asrep_brandon_stark(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
Write-Output (Get-ADUser brandon.stark -Properties DoesNotRequirePreAuth).DoesNotRequirePreAuth
""", cfg)
        assert ok and "True" in out, \
            f"brandon.stark not AS-REP roastable: {out}"

    def test_unconstrained_delegation_sansa_stark(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
Write-Output (Get-ADUser sansa.stark -Properties TrustedForDelegation).TrustedForDelegation
""", cfg)
        assert ok and "True" in out, \
            f"sansa.stark not set for unconstrained delegation: {out}"

    def test_constrained_delegation_jon_snow(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$u = Get-ADUser jon.snow -Properties TrustedToAuthForDelegation,msDS-AllowedToDelegateTo
Write-Output "TrustedToAuth:$($u.TrustedToAuthForDelegation)"
Write-Output "DelegateTo:$($u.'msDS-AllowedToDelegateTo' -join ',')"
""", cfg)
        assert ok and "TrustedToAuth:True" in out, \
            f"jon.snow constrained delegation not set: {out}"
        assert "cifs/winterfell" in out.lower().replace('\r\n', '\n'), \
            f"jon.snow AllowedToDelegateTo missing CIFS/winterfell: {out}"

    def test_castelblack_constrained_delegation_kerb_only(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$c = Get-ADComputer CASTELBLACK -Properties msDS-AllowedToDelegateTo
Write-Output "Count:$($c.'msDS-AllowedToDelegateTo'.Count)"
Write-Output ($c.'msDS-AllowedToDelegateTo' -join ',')
""", cfg)
        assert ok and "Count:0" not in out, \
            f"CASTELBLACK$ constrained delegation not set: {out}"

    def test_scheduled_tasks_three_bots(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match 'bot' }
Write-Output "Count:$($tasks.Count)"
""", cfg)
        assert ok and "Count:3" in out, \
            f"Expected 3 bot scheduled tasks, got: {out}"

    def test_gpo_starkwallpaper_linked_to_domain_root(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module GroupPolicy
$links = (Get-GPInheritance -Target 'DC=north,DC=sevenkingdoms,DC=local' -ErrorAction SilentlyContinue).GpoLinks
$gpo = $links | Where-Object { $_.DisplayName -eq 'StarkWallpaper' }
Write-Output $(if ($gpo) { 'LINKED' } else { 'NOT_LINKED' })
""", cfg)
        assert ok and "LINKED" in out, \
            f"StarkWallpaper GPO not linked to DC=north domain root: {out}"

    def test_anonymous_rpc_restrict_anonymous_0(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$lsa = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa'
Write-Output $lsa.RestrictAnonymous
""", cfg)
        assert ok and out.strip() == "0", \
            f"RestrictAnonymous not 0 on winterfell: {out}"


class TestKingslandingMisconfigs:
    def test_firewall_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip,
            "Write-Output (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count",
            cfg)
        assert ok and out.strip() == "0", f"Firewall still enabled: {out}"

    def test_smb_signing_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip,
            "Write-Output (Get-SmbServerConfiguration).RequireSecuritySignature",
            cfg)
        assert ok and "False" in out, f"SMB signing not disabled: {out}"

    def test_esc10_case1_kdc_registry(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
$v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Kdc' -EA SilentlyContinue).StrongCertificateBindingEnforcement
Write-Output $v
""", cfg)
        assert ok and out.strip() == "0", \
            f"StrongCertificateBindingEnforcement should be 0 on DC01, got: {out}"

    def test_esc10_case2_schannel_registry(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
$v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\Schannel' -EA SilentlyContinue).CertificateMappingMethods
Write-Output $v
""", cfg)
        assert ok and out.strip() == "4", \
            f"CertificateMappingMethods should be 4 on DC01, got: {out}"

    def test_defender_gpo_disable_defender_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module GroupPolicy
$gpo = Get-GPO -Name 'Disable Windows Defender' -ErrorAction SilentlyContinue
Write-Output $(if ($gpo) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, \
            "Ludus built-in 'Disable Windows Defender' GPO not found on kingslanding"

    def test_renly_account_not_delegated(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
Write-Output (Get-ADUser renly.baratheon -Properties AccountNotDelegated).AccountNotDelegated
""", cfg)
        assert ok and "True" in out, \
            f"renly.baratheon AccountNotDelegated not True: {out}"

    def test_robert_in_protected_users(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$m = Get-ADGroupMember 'Protected Users' | Where-Object { $_.SamAccountName -eq 'robert.baratheon' }
Write-Output $(if ($m) { 'YES' } else { 'NO' })
""", cfg)
        assert ok and "YES" in out, \
            "robert.baratheon not in Protected Users group"


class TestMeereenMisconfigs:
    def test_firewall_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip,
            "Write-Output (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count",
            cfg)
        assert ok and out.strip() == "0", f"Firewall still enabled: {out}"

    def test_asrep_missandei(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
Write-Output (Get-ADUser missandei -Properties DoesNotRequirePreAuth).DoesNotRequirePreAuth
""", cfg)
        assert ok and "True" in out, \
            f"missandei not AS-REP roastable: {out}"

    def test_laps_ou_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$ou = Get-ADOrganizationalUnit -Filter { Name -eq 'Laps' } -ErrorAction SilentlyContinue
Write-Output $(if ($ou) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, "LAPS OU not found in essos.local"

    def test_gmsa_dragon_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$g = Get-ADServiceAccount gmsaDragon -ErrorAction SilentlyContinue
Write-Output $(if ($g) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, "gmsaDragon$ service account not found"

    def test_defender_gpo_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module GroupPolicy
$gpo = Get-GPO -Name 'Disable Windows Defender' -ErrorAction SilentlyContinue
Write-Output $(if ($gpo) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, \
            "Ludus built-in 'Disable Windows Defender' GPO not found on meereen"


class TestCastelblackMisconfigs:
    def test_domain_joined_north(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-WmiObject Win32_ComputerSystem).Domain",
            cfg)
        assert ok and "north.sevenkingdoms.local" in out.lower(), \
            f"castelblack not in north.sevenkingdoms.local: {out}"

    def test_firewall_disabled(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count",
            cfg)
        assert ok and out.strip() == "0", f"Firewall still enabled: {out}"

    def test_iis_running(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-Service W3SVC -ErrorAction SilentlyContinue).Status",
            cfg)
        assert ok and "Running" in out, f"IIS (W3SVC) not running: {out}"

    def test_mssql_running(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-Service MSSQLSERVER -ErrorAction SilentlyContinue).Status",
            cfg)
        assert ok and "Running" in out, f"MSSQL not running: {out}"

    def test_defender_rt_disabled(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-MpPreference -ErrorAction SilentlyContinue).DisableRealtimeMonitoring",
            cfg)
        assert ok and "True" in out, \
            f"Windows Defender real-time monitoring still enabled: {out}"

    def test_guest_account_enabled(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip,
            "Write-Output (Get-LocalUser -Name Guest).Enabled",
            cfg)
        assert ok and "True" in out, "Guest account not enabled on castelblack"


class TestBraavosServices:
    def test_domain_joined_essos(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip,
            "Write-Output (Get-WmiObject Win32_ComputerSystem).Domain",
            cfg)
        assert ok and "essos.local" in out.lower(), \
            f"braavos not in essos.local: {out}"

    def test_adcs_running(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip,
            "Write-Output (Get-Service CertSvc -ErrorAction SilentlyContinue).Status",
            cfg)
        assert ok and "Running" in out, f"ADCS (CertSvc) not running: {out}"

    def test_mssql_running(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip,
            "Write-Output (Get-Service MSSQLSERVER -ErrorAction SilentlyContinue).Status",
            cfg)
        assert ok and "Running" in out, f"MSSQL not running on braavos: {out}"

    def test_laps_in_ou(self, cfg):
        # BRAAVOS$ should be in the LAPS OU
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$c = Get-ADComputer BRAAVOS -Properties DistinguishedName -ErrorAction SilentlyContinue
Write-Output $c.DistinguishedName
""", cfg)
        assert ok and "Laps" in out, \
            f"BRAAVOS$ not in LAPS OU. DN: {out}"

    def test_lsa_ppl_enabled(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa').RunAsPPL
Write-Output $v
""", cfg)
        assert ok and out.strip() == "1", \
            f"LSA PPL (RunAsPPL) not enabled on braavos: {out}"

    def test_khal_drogo_local_admin(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$m = Get-LocalGroupMember Administrators | Where-Object { $_.Name -match 'khal' }
Write-Output $(if ($m) { 'YES' } else { 'NO' })
""", cfg)
        assert ok and "YES" in out, \
            "khal.drogo not in local Administrators on braavos"


# ── Kerberos Tests ────────────────────────────────────────────────────────────

class TestKerberos:
    def test_sansa_stark_kerberoastable(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$spns = (Get-ADUser sansa.stark -Properties ServicePrincipalNames).ServicePrincipalNames
Write-Output ($spns -join ',')
""", cfg)
        assert ok and "eyrie" in out.lower(), \
            f"sansa.stark missing HTTP/eyrie SPN: {out}"

    def test_jon_snow_spns_both(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$spns = (Get-ADUser jon.snow -Properties ServicePrincipalNames).ServicePrincipalNames
Write-Output ($spns -join ',')
""", cfg)
        assert ok and "http/thewall" in out.lower(), \
            f"jon.snow missing HTTP/thewall SPN: {out}"
        assert ok and "cifs/thewall" in out.lower(), \
            f"jon.snow missing CIFS/thewall SPN: {out}"

    def test_sql_svc_north_spn(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$spns = (Get-ADUser sql_svc -Properties ServicePrincipalNames).ServicePrincipalNames
Write-Output ($spns -join ',')
""", cfg)
        assert ok and "mssqlsvc/castelblack" in out.lower(), \
            f"north sql_svc missing MSSQLSvc SPN: {out}"

    def test_sql_svc_essos_spn(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$spns = (Get-ADUser sql_svc -Properties ServicePrincipalNames).ServicePrincipalNames
Write-Output ($spns -join ',')
""", cfg)
        assert ok and "mssqlsvc/braavos" in out.lower(), \
            f"essos sql_svc missing MSSQLSvc SPN: {out}"


# ── MSSQL Tests ───────────────────────────────────────────────────────────────

class TestMSSQL:
    def test_castelblack_sa_login(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, f"""
$r = sqlcmd -S localhost -U sa -P '{cfg.castelblack_sa_pass}' -C -Q "SELECT @@SERVERNAME" -h-1 2>&1
Write-Output "Exit:$LASTEXITCODE"
""", cfg)
        assert ok and "Exit:0" in out, \
            f"SA login failed on castelblack: {out}"

    def test_castelblack_jon_snow_sysadmin(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "SELECT IS_SRVROLEMEMBER('sysadmin','NORTH\\jon.snow')" -h-1 2>&1
Write-Output $r
""", cfg)
        assert ok and (re.search(r'^\s*1\b', out, re.MULTILINE) or '(1 rows' in out), \
            f"jon.snow not sysadmin on castelblack: {out}"

    def test_castelblack_braavos_linked_server(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "SELECT name FROM sys.servers WHERE name='BRAAVOS' AND is_linked=1" -h-1 2>&1
Write-Output $r
""", cfg)
        assert ok and "BRAAVOS" in out.upper(), \
            f"BRAAVOS linked server not found on castelblack: {out}"

    def test_castelblack_arya_impersonation_master(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "USE master; SELECT COUNT(*) FROM sys.database_permissions dp JOIN sys.database_principals g ON dp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\\arya.stark' AND dp.type='IM'" -h-1 2>&1
Write-Output $r
""", cfg)
        # sqlcmd returns "1\n(1 rows affected)" for count results
        assert ok and (re.search(r'^\s*[1-9]', out, re.MULTILINE) or '(1 rows' in out), \
            f"arya.stark impersonation in master db not found: {out}"

    def test_castelblack_arya_impersonation_msdb(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "USE msdb; SELECT COUNT(*) FROM sys.database_permissions dp JOIN sys.database_principals g ON dp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\\arya.stark' AND dp.type='IM'" -h-1 2>&1
Write-Output $r
""", cfg)
        assert ok and (re.search(r'^\s*[1-9]', out, re.MULTILINE) or '(1 rows' in out), \
            f"arya.stark impersonation in msdb not found: {out}"

    def test_braavos_sa_login(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, f"""
$r = sqlcmd -S localhost -U sa -P '{cfg.braavos_sa_pass}' -C -Q "SELECT @@SERVERNAME" -h-1 2>&1
Write-Output "Exit:$LASTEXITCODE"
""", cfg)
        assert ok and "Exit:0" in out, \
            f"SA login failed on braavos: {out}"

    def test_braavos_castelblack_linked_server(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "SELECT name FROM sys.servers WHERE name='CASTELBLACK' AND is_linked=1" -h-1 2>&1
Write-Output $r
""", cfg)
        assert ok and "CASTELBLACK" in out.upper(), \
            f"CASTELBLACK linked server not found on braavos: {out}"


# ── ADCS Tests ────────────────────────────────────────────────────────────────

class TestADCS:
    def test_certsvc_running(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip,
            "Write-Output (Get-Service CertSvc).Status", cfg)
        assert ok and "Running" in out, "CertSvc not running on braavos"

    def test_esc6_altname_flag(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$r = certutil -getreg policy\\Editflags 2>&1
Write-Output $(if ($r -match 'EDITF_ATTRIBUTESUBJECTALTNAME2') { 'SET' } else { 'NOT_SET' })
""", cfg)
        # Output may be flag name followed by hex value
        assert ok and ("SET" in out or "EDITF_ATTRIBUTESUBJECTALTNAME2" in out), \
            "ESC6: EDITF_ATTRIBUTESUBJECTALTNAME2 flag not set"

    def test_esc11_unencrypted_requests(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$r = certutil -getreg CA\\InterfaceFlags 2>&1
Write-Output $(if ($r -match 'IF_ENFORCEENCRYPTICERTREQUEST') { 'ENFORCED' } else { 'DISABLED' })
""", cfg)
        assert ok and "DISABLED" in out, \
            "ESC11: IF_ENFORCEENCRYPTICERTREQUEST is still set"


# ── ACL Tests ─────────────────────────────────────────────────────────────────

class TestACLPaths:
    def test_varys_genericall_on_adminsdholder(self, cfg):
        """Check AdminSDHolder instead of Domain Admins directly.
        SDPROP resets Domain Admins ACL hourly back to AdminSDHolder template —
        checking AdminSDHolder is the persistent, reliable verification."""
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$adminSDDN = "CN=AdminSDHolder,CN=System,DC=sevenkingdoms,DC=local"
$acl = (Get-Acl "AD:$adminSDDN").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'varys' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, \
            "lord.varys GenericAll on AdminSDHolder ACE missing (SDPROP propagates this to Domain Admins)"

    def test_khal_drogo_genericall_on_viserys(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$acl = (Get-Acl "AD:$(Get-ADUser viserys.targaryen | Select-Object -ExpandProperty DistinguishedName)").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'khal' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, \
            "khal.drogo GenericAll on viserys.targaryen ACE missing"

    def test_gmsa_dragon_genericall_on_drogon(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$gmsaSID = (Get-ADServiceAccount gmsaDragon -Properties objectSid).SID
$drogonDN = (Get-ADUser drogon).DistinguishedName
$acl = (Get-Acl "AD:$drogonDN").Access
# Use SID-based match to avoid regex issues with $ in gmsaDragon$ name
$v = $acl | Where-Object {
    try {
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -eq $gmsaSID.Value -and
        $_.ActiveDirectoryRights -match 'GenericAll'
    } catch { $false }
}
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, \
            "gmsaDragon$ GenericAll on drogon ACE missing"

    def test_khal_drogo_genericall_on_esc4_template(self, cfg):
        """ESC4: khal.drogo has GenericAll on the ESC4 certificate template.
        Run on DC03 (has RSAT/AD module) not braavos (CA server lacks AD tools)."""
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory -ErrorAction Stop
$templateDN = "CN=ESC4,CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
try {
    $acl = (Get-Acl "AD:$templateDN" -ErrorAction Stop).Access
    $v = $acl | Where-Object { $_.IdentityReference.Value -match 'khal' -and $_.ActiveDirectoryRights -match 'GenericAll' }
    Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
} catch { Write-Output "ERROR: $_" }
""", cfg)
        assert ok and "FOUND" in out, \
            f"khal.drogo GenericAll on ESC4 certificate template ACE missing: {out}"


# ── Forest Trust Tests ────────────────────────────────────────────────────────

class TestForestTrust:
    def test_trust_essos_local_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$t = Get-ADTrust -Filter { Name -eq 'essos.local' } -ErrorAction SilentlyContinue
Write-Output $(if ($t) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, \
            "Forest trust to essos.local not found on kingslanding"

    def test_sid_history_enabled(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$t = Get-ADTrust -Filter { Name -eq 'essos.local' } -Properties TrustAttributes
# SID history enabled when TrustAttributes bit 0x04 (Quarantined/SID filtering) is NOT set
# TrustAttributes: 0x08=ForestTransitive, 0x04=Quarantined(SIDFilter), 0x40=TreatAsExternal
$sidHistoryEnabled = -not [bool]($t.TrustAttributes -band 0x04)
Write-Output "SIDHistoryEnabled:$sidHistoryEnabled"
Write-Output "TrustAttributes:$($t.TrustAttributes)"
""", cfg)
        assert ok and "SIDHistoryEnabled:True" in out, \
            f"SID history not enabled on sevenkingdoms<->essos trust: {out}"

    def test_trust_sevenkingdoms_exists_on_meereen(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$t = Get-ADTrust -Filter { Name -like '*sevenkingdoms*' } -ErrorAction SilentlyContinue
Write-Output $(if ($t) { 'EXISTS' } else { 'MISSING' })
""", cfg)
        assert ok and "EXISTS" in out, \
            "Forest trust to sevenkingdoms.local not found on meereen"


# ── ACL Chain Tests ───────────────────────────────────────────────────────────

class TestACLChainsSevenkingdoms:
    """Full sevenkingdoms.local ACL attack chain verification."""

    def test_acl_chain_full(self, cfg):
        """Run full sevenkingdoms + essos ACL chain checks via validate_goad functions."""
        results = run_acl_chain_checks(cfg)
        assert_results(results)

    def test_tywin_forcechangepassword_jaime(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$jaimeDN = (Get-ADUser 'jaime.lannister').DistinguishedName
$acl = (Get-Acl "AD:$jaimeDN").Access
$v = $acl | Where-Object { $_.ActiveDirectoryRights -match 'ExtendedRight' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "tywin→jaime ForceChangePassword ACE missing"

    def test_jaime_genericwrite_joffrey(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$dn = (Get-ADUser 'joffrey.baratheon').DistinguishedName
$acl = (Get-Acl "AD:$dn").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'jaime' -and ($_.ActiveDirectoryRights -match 'WriteProperty' -or $_.ActiveDirectoryRights -match 'GenericWrite') }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "jaime→joffrey GenericWrite ACE missing"

    def test_joffrey_writedacl_tyron(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$dn = (Get-ADUser 'tyron.lannister').DistinguishedName
$acl = (Get-Acl "AD:$dn").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'joffrey' -and $_.ActiveDirectoryRights -match 'WriteDacl' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "joffrey→tyron WriteDacl ACE missing"

    def test_stannis_genericall_kingslanding_computer(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$comp = Get-ADComputer 'kingslanding' -EA SilentlyContinue
if (-not $comp) { Write-Output 'MISSING'; return }
$acl = (Get-Acl "AD:$($comp.DistinguishedName)").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'stannis' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "stannis→kingslanding$ GenericAll ACE missing"

    def test_renly_writedacl_crownlands_ou(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$ou = Get-ADOrganizationalUnit -Filter { Name -eq 'Crownlands' } -EA SilentlyContinue
if (-not $ou) { Write-Output 'MISSING'; return }
$acl = (Get-Acl "AD:$($ou.DistinguishedName)").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'renly' -and $_.ActiveDirectoryRights -match 'WriteDacl' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "renly→OU=Crownlands WriteDacl ACE missing"


class TestACLChainsEssos:
    """Full essos.local ACL attack chain verification."""

    def test_khal_genericall_viserys(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = (Get-ADUser 'viserys.targaryen').DistinguishedName
$acl = (Get-Acl "AD:$dn").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'khal' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "khal.drogo→viserys.targaryen GenericAll ACE missing"

    def test_spys_genericall_jorah(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = (Get-ADUser 'jorah.mormont').DistinguishedName
$acl = (Get-Acl "AD:$dn").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'Spys' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "Spys→jorah.mormont GenericAll ACE missing"

    def test_missandei_genericall_khal(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = (Get-ADUser 'khal.drogo').DistinguishedName
$acl = (Get-Acl "AD:$dn").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'missandei' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "missandei→khal.drogo GenericAll ACE missing"

    def test_dragonsfriends_genericwrite_braavos_computer(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$comp = Get-ADComputer 'braavos' -EA SilentlyContinue
if (-not $comp) { Write-Output 'MISSING'; return }
$acl = (Get-Acl "AD:$($comp.DistinguishedName)").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'DragonsFriends' -and ($_.ActiveDirectoryRights -match 'WriteProperty' -or $_.ActiveDirectoryRights -match 'GenericWrite') }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "DragonsFriends→braavos$ GenericWrite ACE missing"


# ── ADCS Template Tests ───────────────────────────────────────────────────────

class TestADCSTemplates:
    """Verify ADCS ESC certificate templates are published."""

    def test_esc_templates_exist(self, cfg):
        results = run_adcs_template_checks(cfg)
        assert_results(results)

    def test_esc1_template_published(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = "CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
$t = Get-ADObject -Filter "Name -eq 'ESC1'" -SearchBase $dn -EA SilentlyContinue
Write-Output $(if ($t) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "ESC1 certificate template not published"

    def test_esc4_template_published(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = "CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
$t = Get-ADObject -Filter "Name -eq 'ESC4'" -SearchBase $dn -EA SilentlyContinue
Write-Output $(if ($t) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "ESC4 certificate template not published"

    def test_esc9_template_published(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = "CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
$t = Get-ADObject -Filter "Name -eq 'ESC9'" -SearchBase $dn -EA SilentlyContinue
Write-Output $(if ($t) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "ESC9 certificate template not published"

    def test_esc13_template_published(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$dn = "CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
$t = Get-ADObject -Filter "Name -eq 'ESC13'" -SearchBase $dn -EA SilentlyContinue
Write-Output $(if ($t) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "ESC13 certificate template not published"


# ── MSSQL Extended Tests ──────────────────────────────────────────────────────

class TestMSSQLExtended:
    """Verify extended MSSQL attack paths (ExecuteAs, sysadmin)."""

    def test_mssql_extended_checks(self, cfg):
        results = run_mssql_extended_checks(cfg)
        assert_results(results)

    def test_castelblack_samwell_impersonate_sa(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, rf"""
$r = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\samwell.tarly' AND sp.type='IM'" -h-1 2>&1
Write-Output ($r | Out-String)
""", cfg)
        assert ok and re.search(r'\b[1-9]', out or ""), \
            f"samwell.tarly cannot impersonate sa on castelblack: {out}"

    def test_castelblack_brandon_impersonate_jon_snow(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, rf"""
$r = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\brandon.stark' AND sp.type='IM'" -h-1 2>&1
Write-Output ($r | Out-String)
""", cfg)
        assert ok and re.search(r'\b[1-9]', out or ""), \
            f"brandon.stark cannot impersonate jon.snow on castelblack: {out}"

    def test_braavos_khal_drogo_sysadmin(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "SELECT IS_SRVROLEMEMBER('sysadmin','ESSOS\khal.drogo')" -h-1 2>&1
Write-Output ($r | Out-String)
""", cfg)
        assert ok and "1" in (out or ""), \
            f"khal.drogo is not sysadmin on braavos: {out}"

    def test_braavos_jorah_impersonate_sa(self, cfg):
        ok, out = winrm_ps(cfg.srv03_ip, r"""
$r = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='ESSOS\jorah.mormont' AND sp.type='IM'" -h-1 2>&1
Write-Output ($r | Out-String)
""", cfg)
        assert ok and re.search(r'\b[1-9]', out or ""), \
            f"jorah.mormont cannot impersonate sa on braavos: {out}"


# ── Cross-Domain Group Tests ──────────────────────────────────────────────────

class TestCrossDomainGroups:
    """Verify cross-forest FSP group memberships via validate_goad functions."""

    def test_cross_domain_groups(self, cfg):
        results = run_cross_domain_group_checks(cfg)
        assert_results(results)

    def test_dragonsfriends_has_two_members(self, cfg):
        """DragonsFriends should have both tyron.lannister (sevenkingdoms FSP) and daenerys."""
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup DragonsFriends -Properties Members -EA SilentlyContinue
Write-Output "Count:$($grp.Members.Count)"
""", cfg)
        try:
            cnt = int(out.split("Count:")[1].strip())
            assert ok and cnt >= 2, \
                f"DragonsFriends should have ≥2 members (tyron.lannister + daenerys.targaryen), got {cnt}"
        except (IndexError, ValueError):
            assert False, f"Could not parse count: {out}"


# ── Password Policy Tests ─────────────────────────────────────────────────────

class TestPasswordPolicies:
    """Verify weak password policies are configured on all three domains."""

    def test_password_policies(self, cfg):
        results = run_password_policy_checks(cfg)
        assert_results(results)

    def test_sevenkingdoms_complexity_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$pol = Get-ADDefaultDomainPasswordPolicy -Identity 'DC=sevenkingdoms,DC=local'
Write-Output "ComplexityEnabled:$($pol.ComplexityEnabled)"
""", cfg)
        assert ok and "ComplexityEnabled:False" in out, \
            f"sevenkingdoms.local password complexity should be disabled: {out}"

    def test_north_complexity_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$pol = Get-ADDefaultDomainPasswordPolicy -Identity 'DC=north,DC=sevenkingdoms,DC=local'
Write-Output "ComplexityEnabled:$($pol.ComplexityEnabled)"
""", cfg)
        assert ok and "ComplexityEnabled:False" in out, \
            f"north.sevenkingdoms.local password complexity should be disabled: {out}"

    def test_essos_complexity_disabled(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$pol = Get-ADDefaultDomainPasswordPolicy -Identity 'DC=essos,DC=local'
Write-Output "ComplexityEnabled:$($pol.ComplexityEnabled)"
""", cfg)
        assert ok and "ComplexityEnabled:False" in out, \
            f"essos.local password complexity should be disabled: {out}"


# ── NTLM & Auth Checks ────────────────────────────────────────────────────────

class TestNTLMAndAuth:
    def test_winterfell_credential_manager_castelblack(self, cfg):
        """robb.stark has TERMSRV/castelblack stored in Credential Manager.
        The credential is stored in robb.stark's user vault, not the current WinRM session user."""
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$robbVault = 'C:\Users\robb.stark\AppData\Local\Microsoft\Vault'
$vaultFiles = Get-ChildItem $robbVault -Recurse -EA SilentlyContinue
$hasCredentials = [bool]($vaultFiles | Where-Object { $_.Name -match 'vpol|vsch|\{' })
Write-Output $(if ($hasCredentials) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, \
            "Credential Manager vault for robb.stark not found on winterfell"

    def test_meereen_ntlm_downgrade(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
$lm = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -EA SilentlyContinue).LmCompatibilityLevel
Write-Output "LmCompatibilityLevel:$lm"
""", cfg)
        # LmCompatibilityLevel=2 means NTLM v1 is sent (downgrade from NTLMv2)
        # null/absent also allows downgrade in default config
        assert ok, f"WinRM failed on meereen: {out}"


# ── SYSVOL & Files Tests ──────────────────────────────────────────────────────

class TestSysvolAndFiles:
    """Verify SYSVOL scripts and file deployments expose credentials."""

    def test_sysvol_and_files(self, cfg):
        results = run_sysvol_and_files_checks(cfg)
        assert_results(results)

    def test_sysvol_script_exists(self, cfg):
        ok, out = winrm_ps(cfg.dc02_ip, r"""
Write-Output $(if (Test-Path 'C:\Windows\SYSVOL\domain\scripts\script.ps1') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "SYSVOL scripts/script.ps1 not deployed on winterfell"

    def test_sysvol_script_has_credentials(self, cfg):
        """script.ps1 in SYSVOL should contain jeor.mormont credentials (file disclosure vuln)."""
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$content = Get-Content 'C:\Windows\SYSVOL\domain\scripts\script.ps1' -Raw -EA SilentlyContinue
Write-Output $(if ($content -match 'jeor|mormont|password') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "SYSVOL script.ps1 does not contain expected credential disclosure"

    def test_arya_txt_in_all_share(self, cfg):
        """arya.txt deployed to castelblack all share (file enumeration practice)."""
        ok, out = winrm_ps(cfg.srv02_ip, r"""
Write-Output $(if (Test-Path 'C:\shares\all\arya.txt') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "arya.txt not found in castelblack all share"


# ── LAPS Reader Permission Tests ──────────────────────────────────────────────

class TestLAPSReaderPermissions:
    """Verify LAPS reader permissions (jorah.mormont and Spys can read braavos$ password)."""

    def test_laps_reader_permissions(self, cfg):
        results = run_laps_reader_checks(cfg)
        assert_results(results)

    def test_braavos_in_laps_ou(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$comp = Get-ADComputer braavos -Properties DistinguishedName -EA SilentlyContinue
Write-Output $(if ($comp -and $comp.DistinguishedName -match 'Laps') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "braavos$ is not in the LAPS OU in essos.local"

    def test_jorah_mormont_is_laps_reader(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$braavos = Get-ADComputer braavos -EA SilentlyContinue
if (-not $braavos) { Write-Output 'MISSING'; return }
$acl = (Get-Acl "AD:$($braavos.DistinguishedName)" -EA SilentlyContinue).Access
$jorah = Get-ADUser jorah.mormont -Properties objectSid -EA SilentlyContinue
if (-not $jorah) { Write-Output 'MISSING'; return }
$sid = New-Object System.Security.Principal.SecurityIdentifier($jorah.objectSid)
$found = [bool]($acl | Where-Object {
    try { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -eq $sid.Value } catch { $false }
})
Write-Output $(if ($found) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "jorah.mormont does not have LAPS read access on braavos$"


# ── Additional Local Admin / Coercion Tests ───────────────────────────────────

class TestLocalAdminMembership:
    """Verify local administrator group memberships across all hosts."""

    def test_kingslanding_robert_baratheon_local_admin(self, cfg):
        ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$admins = Get-ADGroupMember Administrators -EA SilentlyContinue | Select-Object -ExpandProperty SamAccountName
Write-Output $(if ($admins -contains 'robert.baratheon') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "robert.baratheon is not in Administrators group on kingslanding"

    def test_castelblack_jeor_mormont_local_admin(self, cfg):
        ok, out = winrm_ps(cfg.srv02_ip, r"""
$admins = Get-LocalGroupMember Administrators -EA SilentlyContinue
Write-Output $(if ($admins | Where-Object { $_.Name -match 'jeor.mormont' }) { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "jeor.mormont is not local admin on castelblack"

    def test_meereen_daenerys_local_admin(self, cfg):
        ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$admins = Get-ADGroupMember Administrators -EA SilentlyContinue | Select-Object -ExpandProperty SamAccountName
Write-Output $(if ($admins -contains 'daenerys.targaryen') { 'FOUND' } else { 'MISSING' })
""", cfg)
        assert ok and "FOUND" in out, "daenerys.targaryen is not in Administrators group on meereen"

    def test_coercion_print_spooler_all_hosts(self, cfg):
        """Print Spooler should be running on all GOAD hosts for coercion attacks."""
        for ip, label in [
            (cfg.dc01_ip, "kingslanding"),
            (cfg.dc02_ip, "winterfell"),
            (cfg.dc03_ip, "meereen"),
            (cfg.srv02_ip, "castelblack"),
            (cfg.srv03_ip, "braavos"),
        ]:
            ok, out = winrm_ps(ip, r"""
Write-Output (Get-Service Spooler -EA SilentlyContinue).Status
""", cfg)
            assert ok and "Running" in out, \
                f"Print Spooler not running on {label} — coercion attacks won't work: {out}"

    def test_coercion_webclient_all_hosts(self, cfg):
        """WebClient service should be running on all GOAD hosts for WebDAV coercion."""
        for ip, label in [
            (cfg.dc01_ip, "kingslanding"),
            (cfg.dc02_ip, "winterfell"),
            (cfg.dc03_ip, "meereen"),
            (cfg.srv02_ip, "castelblack"),
            (cfg.srv03_ip, "braavos"),
        ]:
            ok, out = winrm_ps(ip, r"""
Write-Output (Get-Service WebClient -EA SilentlyContinue).Status
""", cfg)
            assert ok and "Running" in out, \
                f"WebClient not running on {label} — WebDAV coercion won't work: {out}"
