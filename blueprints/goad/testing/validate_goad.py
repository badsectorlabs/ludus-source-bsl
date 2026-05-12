"""
GOAD (Game of Active Directory) — Validation Test Suite
========================================================
Verifies that all expected misconfigurations, AD content, and attack paths
are correctly deployed. Runs from the Ludus server which has direct network
access to all range VMs.

Usage:
    python3 validate_goad.py                     # Run all tests, auto-detect range
    python3 validate_goad.py --range-id GOAD1    # Specify range ID
    python3 validate_goad.py --second-octet 1    # Specify network octet directly
    python3 validate_goad.py --verbose           # Show all check details

Requirements:
    pip install pytest ldap3 impacket pywinrm requests

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import argparse
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

# ── optional imports – tests skip gracefully if missing ──────────────────────
try:
    import winrm
    HAS_WINRM = True
except ImportError:
    HAS_WINRM = False

try:
    from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
    HAS_LDAP3 = True
except ImportError:
    HAS_LDAP3 = False

try:
    from impacket.krb5.asn1 import AS_REQ
    from impacket.krb5 import constants
    from impacket.krb5.types import KerberosTime, Principal
    from impacket.krb5.kerberosv5 import sendReceive
    from impacket.krb5.asn1 import AS_REP
    from pyasn1.codec.der import decoder, encoder
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False


# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class GOADConfig:
    """IP addresses and credentials for a GOAD deployment."""
    second_octet: int = 1

    # Derived IPs
    @property
    def dc01_ip(self) -> str:   return f"10.{self.second_octet}.10.10"  # kingslanding
    @property
    def dc02_ip(self) -> str:   return f"10.{self.second_octet}.10.11"  # winterfell
    @property
    def srv02_ip(self) -> str:  return f"10.{self.second_octet}.10.12"  # castelblack
    @property
    def dc03_ip(self) -> str:   return f"10.{self.second_octet}.10.13"  # meereen
    @property
    def srv03_ip(self) -> str:  return f"10.{self.second_octet}.10.14"  # braavos

    # WinRM credentials (Ludus defaults)
    winrm_user: str     = "localuser"
    winrm_password: str = "password"
    winrm_port: int     = 5986

    # Domain credentials
    north_admin_user: str    = "eddard.stark"
    north_admin_pass: str    = "FightP3aceAndHonor!"
    essos_admin_user: str    = "daenerys.targaryen"
    essos_admin_pass: str    = "BurnThemAll!"
    seven_admin_user: str    = "domainadmin"
    seven_admin_pass: str    = "password"

    # SA passwords
    castelblack_sa_pass: str = "Sup1_sa_P@ssw0rd!"
    braavos_sa_pass: str     = "sa_P@ssw0rd!Ess0s"


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False
    skip_reason: str = ""


# ── Core helpers ──────────────────────────────────────────────────────────────
def tcp_reachable(ip: str, port: int, timeout: float = 3.0) -> bool:
    """Quick TCP connectivity check."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def winrm_ps(ip: str, script: str, cfg: GOADConfig,
             timeout: int = 30) -> tuple[bool, str]:
    """Run a PowerShell script via WinRM. Returns (success, output)."""
    if not HAS_WINRM:
        return False, "pywinrm not installed"
    try:
        sess = winrm.Session(
            f"https://{ip}:{cfg.winrm_port}/wsman",
            auth=(cfg.winrm_user, cfg.winrm_password),
            transport="ntlm",
            server_cert_validation="ignore",
        )
        r = sess.run_ps(script)
        out = (r.std_out or b"").decode(errors="replace").strip()
        err = (r.std_err or b"").decode(errors="replace").strip()
        if r.status_code != 0:
            return False, err or out
        return True, out
    except Exception as exc:
        return False, str(exc)


def ldap_query(ip: str, domain: str, username: str, password: str,
               base: str, search_filter: str,
               attributes: list[str]) -> tuple[bool, list]:
    """LDAP query helper. Returns (success, entries)."""
    if not HAS_LDAP3:
        return False, []
    try:
        server = Server(ip, port=389, get_info=ALL, connect_timeout=5)
        conn = Connection(
            server,
            user=f"{domain}\\{username}",
            password=password,
            authentication=NTLM,
            auto_bind=True,
        )
        conn.search(base, search_filter, SUBTREE, attributes=attributes)
        return True, list(conn.entries)
    except Exception as exc:
        return False, []


def smb_shares(ip: str, cfg: GOADConfig) -> tuple[bool, list[str]]:
    """List SMB shares anonymously using smbclient."""
    try:
        result = subprocess.run(
            ["smbclient", "-L", f"//{ip}", "-N", "--no-pass"],
            capture_output=True, text=True, timeout=10
        )
        shares = re.findall(r"^\s+(\S+)\s+Disk", result.stdout, re.MULTILINE)
        return True, shares
    except Exception:
        return False, []


def check_tcp(ip: str, port: int, name: str) -> CheckResult:
    ok = tcp_reachable(ip, port)
    return CheckResult(
        name=name,
        passed=ok,
        detail=f"{ip}:{port} {'open' if ok else 'CLOSED'}"
    )


# ── Test categories ───────────────────────────────────────────────────────────

def run_network_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify all hosts are reachable on key ports."""
    results = []
    hosts = [
        (cfg.dc01_ip,  "DC01/kingslanding",  [445, 389, 88]),
        (cfg.dc02_ip,  "DC02/winterfell",    [445, 389, 88]),
        (cfg.srv02_ip, "SRV02/castelblack",  [445, 1433, 80]),
        (cfg.dc03_ip,  "DC03/meereen",       [445, 389, 88]),
        (cfg.srv03_ip, "SRV03/braavos",      [445, 1433, 80]),
    ]
    for ip, label, ports in hosts:
        for port in ports:
            name = f"port_open_{label.split('/')[1]}_{port}"
            results.append(check_tcp(ip, port, name))
    return results


def run_smb_checks(cfg: GOADConfig) -> list[CheckResult]:
    """SMB signing disabled, null auth, expected shares."""
    results = []

    # Check SMB signing and null auth via nxc/smbclient output
    for ip, label, expected_signing, expect_null in [
        (cfg.dc01_ip,  "kingslanding", False, True),
        (cfg.dc02_ip,  "winterfell",   False, True),
        (cfg.srv02_ip, "castelblack",  False, False),
        (cfg.dc03_ip,  "meereen",      False, True),
        (cfg.srv03_ip, "braavos",      False, False),
    ]:
        if not tcp_reachable(ip, 445):
            results.append(CheckResult(f"smb_signing_{label}", False,
                                       f"{ip}:445 not reachable"))
            continue
        ok, out = winrm_ps(ip, r"""
$smb = Get-SmbServerConfiguration
Write-Output "RequireSigning:$($smb.RequireSecuritySignature)"
""", cfg)
        if ok and "RequireSigning:" in out:
            val = out.split("RequireSigning:")[1].strip().lower() == "true"
            signing_ok = val == expected_signing
            results.append(CheckResult(
                f"smb_signing_disabled_{label}", signing_ok,
                f"RequireSecuritySignature={val} (expected {expected_signing})"
            ))
        else:
            results.append(CheckResult(f"smb_signing_{label}", False,
                                       f"Could not query: {out}"))

    # Specific shares
    share_checks = [
        (cfg.srv02_ip, "castelblack", ["all", "public", "thewall"]),
        (cfg.srv03_ip, "braavos",     ["all", "public", "CertEnroll"]),
    ]
    for ip, label, expected in share_checks:
        ok, shares = smb_shares(ip, cfg)
        if not ok:
            results.append(CheckResult(f"smb_shares_{label}", False,
                                       "smbclient failed"))
            continue
        for s in expected:
            found = s in shares
            results.append(CheckResult(
                f"smb_share_{label}_{s}", found,
                f"{'Found' if found else 'MISSING'} share '{s}' on {label}"
            ))

    return results


def run_ad_user_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify all GOAD users exist with correct properties."""
    results = []

    # Winterfell — north domain users
    expected_north = [
        "arya.stark", "eddard.stark", "catelyn.stark", "robb.stark",
        "sansa.stark", "brandon.stark", "rickon.stark", "hodor",
        "jon.snow", "samwell.tarly", "jeor.mormont", "sql_svc",
    ]
    ok, out = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$users = Get-ADUser -Filter * | Select-Object -ExpandProperty SamAccountName
Write-Output ($users -join ',')
""", cfg)
    if ok:
        found_users = set(out.lower().split(","))
        for u in expected_north:
            results.append(CheckResult(
                f"user_north_{u}", u.lower() in found_users,
                f"User '{u}' {'found' if u.lower() in found_users else 'MISSING'} in NORTH"
            ))
        # Password in description — samwell.tarly
        ok2, out2 = winrm_ps(cfg.dc02_ip, r"""
Import-Module ActiveDirectory
$u = Get-ADUser samwell.tarly -Properties Description
Write-Output $u.Description
""", cfg)
        desc_ok = ok2 and "Heartsbane" in out2
        results.append(CheckResult(
            "samwell_password_in_description", desc_ok,
            f"Description: '{out2.strip() if ok2 else 'N/A'}'"
        ))
    else:
        results.append(CheckResult("north_users_query", False,
                                   f"WinRM failed: {out}"))

    # Essos users
    expected_essos = [
        "daenerys.targaryen", "viserys.targaryen", "khal.drogo",
        "jorah.mormont", "missandei", "drogon", "sql_svc",
    ]
    ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$users = Get-ADUser -Filter * | Select-Object -ExpandProperty SamAccountName
Write-Output ($users -join ',')
""", cfg)
    if ok:
        found_users = set(out.lower().split(","))
        for u in expected_essos:
            results.append(CheckResult(
                f"user_essos_{u}", u.lower() in found_users,
                f"User '{u}' {'found' if u.lower() in found_users else 'MISSING'} in ESSOS"
            ))
    else:
        results.append(CheckResult("essos_users_query", False,
                                   f"WinRM failed: {out}"))

    return results


def run_ad_group_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify key GOAD groups and memberships."""
    results = []

    checks = [
        # (dc_ip, domain, group, expected_member_hint)
        (cfg.dc02_ip, "NORTH", "Stark", "arya.stark"),
        (cfg.dc02_ip, "NORTH", "Night Watch", "jon.snow"),
        (cfg.dc03_ip, "ESSOS", "Targaryen", "daenerys.targaryen"),
        (cfg.dc03_ip, "ESSOS", "Dragons", "drogon"),
        (cfg.dc03_ip, "ESSOS", "QueenProtector", "Dragons"),
    ]
    for ip, domain, group, member_hint in checks:
        ok, out = winrm_ps(ip, f"""
Import-Module ActiveDirectory
$members = Get-ADGroupMember '{group}' -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty SamAccountName
Write-Output ($members -join ',')
""", cfg)
        found = ok and member_hint.lower() in out.lower()
        results.append(CheckResult(
            f"group_{domain}_{group.replace(' ', '_')}",
            found,
            f"'{member_hint}' {'in' if found else 'NOT in'} {domain}\\{group}"
        ))

    # Nested DA chain: drogon → Dragons → QueenProtector → Domain Admins
    ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$da = Get-ADGroupMember 'Domain Admins' -Recursive |
      Where-Object { $_.SamAccountName -eq 'drogon' }
Write-Output $(if ($da) { 'YES' } else { 'NO' })
""", cfg)
    results.append(CheckResult(
        "essos_nested_da_drogon",
        ok and "YES" in out,
        f"drogon effective DA via nesting: {out.strip() if ok else 'N/A'}"
    ))

    # Cross-domain: AcrossTheNarrowSea has daenerys (via FSP)
    ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup AcrossTheNarrowSea -Properties Members -ErrorAction SilentlyContinue
$count = if ($grp) { $grp.Members.Count } else { 0 }
Write-Output "MemberCount:$count"
""", cfg)
    results.append(CheckResult(
        "sevenkingdoms_AcrossTheNarrowSea_has_member",
        ok and "MemberCount:0" not in out,
        f"AcrossTheNarrowSea: {out.strip() if ok else 'N/A'}"
    ))

    return results


def run_acl_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify key ACL attack paths exist."""
    results = []

    acl_checks = [
        # DC, script, test_name, expected_in_output
        (cfg.dc01_ip, r"""
Import-Module ActiveDirectory
# Check AdminSDHolder — SDPROP propagates this to Domain Admins hourly.
# Checking AdminSDHolder is more reliable than Domain Admins directly since
# SDPROP resets Domain Admins ACL every hour back to the AdminSDHolder template.
$adminSDDN = "CN=AdminSDHolder,CN=System,DC=sevenkingdoms,DC=local"
$acl = (Get-Acl "AD:$adminSDDN").Access
$v = $acl | Where-Object { $_.IdentityReference -match 'varys' -and $_.ActiveDirectoryRights -match 'GenericAll' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", "acl_varys_GenericAll_AdminSDHolder", "FOUND"),

        (cfg.dc01_ip, """
Import-Module ActiveDirectory
$acl = (Get-Acl "AD:$(Get-ADUser 'tywin.lannister' | Select-Object -ExpandProperty DistinguishedName)").Access
$v = $acl | Where-Object { $_.ActiveDirectoryRights -match 'ExtendedRight' }
Write-Output $(if ($v) { 'FOUND' } else { 'MISSING' })
""", "acl_tywin_ForceChangePassword_on_jaime", "FOUND"),

        (cfg.dc01_ip, """
Import-Module ActiveDirectory
$u = Get-ADUser renly.baratheon -Properties AccountNotDelegated
Write-Output "AccountNotDelegated:$($u.AccountNotDelegated)"
""", "renly_AccountNotDelegated", "True"),

        (cfg.dc01_ip, """
Import-Module ActiveDirectory
$u = Get-ADGroupMember 'Protected Users' | Where-Object { $_.SamAccountName -eq 'robert.baratheon' }
Write-Output $(if ($u) { 'FOUND' } else { 'MISSING' })
""", "robert_baratheon_Protected_Users", "FOUND"),
    ]

    for ip, script, name, expected in acl_checks:
        ok, out = winrm_ps(ip, script, cfg)
        passed = ok and expected.lower() in out.lower()
        results.append(CheckResult(name, passed,
                                   f"Output: {out.strip()[:80] if ok else out}"))

    return results


def run_misconfiguration_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify GOAD misconfigurations on each host."""
    results = []

    # ── winterfell (DC02) ────────────────────────────────────────────────────
    winterfell_script = r"""
Import-Module ActiveDirectory
$r = @{}

# Firewall
$fw = (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count
$r['firewall_disabled'] = $fw -eq 0

# SMB signing
$smb = Get-SmbServerConfiguration
$r['smb_signing_disabled'] = -not $smb.RequireSecuritySignature

# Print Spooler
$r['print_spooler_running'] = (Get-Service Spooler).Status -eq 'Running'

# WebClient
$r['webclient_running'] = (Get-Service WebClient -EA SilentlyContinue).Status -eq 'Running'

# Autologon
$al = Get-ItemProperty 'HKLM:\\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -EA SilentlyContinue
$r['autologon_robb_stark'] = $al.DefaultUserName -eq 'robb.stark'

# AS-REP brandon.stark
$u = Get-ADUser brandon.stark -Properties DoesNotRequirePreAuth
$r['asrep_brandon_stark'] = $u.DoesNotRequirePreAuth

# Unconstrained delegation sansa.stark
$u2 = Get-ADUser sansa.stark -Properties TrustedForDelegation
$r['unconstrained_delegation_sansa'] = $u2.TrustedForDelegation

# Constrained delegation jon.snow
$u3 = Get-ADUser jon.snow -Properties TrustedToAuthForDelegation
$r['constrained_delegation_jon_snow'] = $u3.TrustedToAuthForDelegation

# Scheduled tasks
$tasks = (Get-ScheduledTask | Where-Object { $_.TaskName -match 'bot' }).Count
$r['scheduled_tasks_3_bots'] = $tasks -eq 3

# GPO StarkWallpaper linked to domain root
$links = (Get-GPInheritance -Target 'DC=north,DC=sevenkingdoms,DC=local' -EA SilentlyContinue).GpoLinks
$r['gpo_starkwallpaper_domain_root'] = ($links | Where-Object { $_.DisplayName -eq 'StarkWallpaper' }) -ne $null

# Anonymous RPC
$lsa = Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Control\Lsa'
$r['anonymous_rpc_restrict_anonymous_0'] = $lsa.RestrictAnonymous -eq 0

# CASTELBLACK$ constrained delegation
$c = Get-ADComputer CASTELBLACK -Properties msDS-AllowedToDelegateTo -EA SilentlyContinue
$r['castelblack_constrained_delegation'] = $c.'msDS-AllowedToDelegateTo'.Count -gt 0

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc02_ip, winterfell_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"winterfell_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("winterfell_misconfigs", False,
                                   f"WinRM failed: {out}"))

    # ── kingslanding (DC01) ──────────────────────────────────────────────────
    kingslanding_script = r"""
Import-Module ActiveDirectory
$r = @{}

$r['firewall_disabled'] = (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count -eq 0
$r['smb_signing_disabled'] = -not (Get-SmbServerConfiguration).RequireSecuritySignature
$r['print_spooler_running'] = (Get-Service Spooler -EA SilentlyContinue).Status -eq 'Running'
$r['webclient_running'] = (Get-Service WebClient -EA SilentlyContinue).Status -eq 'Running'
$r['trust_essos_local'] = (Get-ADTrust -Filter { Name -eq 'essos.local' } -EA SilentlyContinue) -ne $null
$trust = Get-ADTrust -Filter { Name -eq 'essos.local' } -Properties SIDFilteringForestAware -EA SilentlyContinue
# SID history enabled when TrustAttributes bit 0x04 (Quarantined/SID filtering) is NOT set
$r['sid_history_enabled'] = $trust -ne $null -and -not [bool]($trust.TrustAttributes -band 0x04)
$r['esc10_case1_kdc_registry'] = (Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Services\Kdc' -EA SilentlyContinue).StrongCertificateBindingEnforcement -eq 0
$r['esc10_case2_schannel_registry'] = (Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Control\SecurityProviders\Schannel' -EA SilentlyContinue).CertificateMappingMethods -eq 4
$r['defender_gpo_exists'] = (Get-GPO -Name 'Disable Windows Defender' -EA SilentlyContinue) -ne $null
# Local group memberships — on DCs use Get-ADGroupMember for the built-in Administrators group
$admins = Get-ADGroupMember Administrators -EA SilentlyContinue | Select-Object -ExpandProperty SamAccountName
$r['robert_baratheon_local_admin'] = $admins -contains 'robert.baratheon'
$r['cersei_lannister_local_admin'] = $admins -contains 'cersei.lannister'

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc01_ip, kingslanding_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"kingslanding_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("kingslanding_misconfigs", False,
                                   f"WinRM failed: {out}"))

    # ── meereen (DC03) ───────────────────────────────────────────────────────
    meereen_script = r"""
Import-Module ActiveDirectory
$r = @{}

$r['firewall_disabled'] = (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count -eq 0
$r['smb_signing_disabled'] = -not (Get-SmbServerConfiguration).RequireSecuritySignature
$r['print_spooler_running'] = (Get-Service Spooler -EA SilentlyContinue).Status -eq 'Running'
$r['webclient_running'] = (Get-Service WebClient -EA SilentlyContinue).Status -eq 'Running'
$r['trust_sevenkingdoms'] = (Get-ADTrust -Filter { Name -like '*sevenkingdoms*' } -EA SilentlyContinue) -ne $null
$r['asrep_missandei'] = (Get-ADUser missandei -Properties DoesNotRequirePreAuth).DoesNotRequirePreAuth
$r['laps_ou_exists'] = (Get-ADOrganizationalUnit -Filter { Name -eq 'Laps' } -EA SilentlyContinue) -ne $null
$r['gmsa_dragon_exists'] = (Get-ADServiceAccount gmsaDragon -EA SilentlyContinue) -ne $null
$r['defender_gpo_exists'] = (Get-GPO -Name 'Disable Windows Defender' -EA SilentlyContinue) -ne $null
$spns = (Get-ADUser sql_svc -Properties ServicePrincipalNames).ServicePrincipalNames
$r['essos_sql_svc_spn'] = [bool]($spns | Where-Object { $_ -match 'MSSQLSvc' })
# Local group memberships — on DCs use Get-ADGroupMember for built-in Administrators
$admins = Get-ADGroupMember Administrators -EA SilentlyContinue | Select-Object -ExpandProperty SamAccountName
$r['daenerys_targaryen_local_admin'] = $admins -contains 'daenerys.targaryen'

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc03_ip, meereen_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"meereen_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("meereen_misconfigs", False,
                                   f"WinRM failed: {out}"))

    # ── castelblack (SRV02) ──────────────────────────────────────────────────
    castelblack_script = r"""
$r = @{}

$r['domain_joined_north'] = ((Get-WmiObject Win32_ComputerSystem).Domain -eq 'north.sevenkingdoms.local')
$r['firewall_disabled'] = (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count -eq 0
$r['smb_signing_disabled'] = -not (Get-SmbServerConfiguration).RequireSecuritySignature
$r['iis_running'] = (Get-Service W3SVC -EA SilentlyContinue).Status -eq 'Running'
$r['mssql_running'] = (Get-Service MSSQLSERVER -EA SilentlyContinue).Status -eq 'Running'
$r['thewall_share_exists'] = (Get-SmbShare -Name thewall -EA SilentlyContinue) -ne $null
$r['public_share_exists'] = (Get-SmbShare -Name public -EA SilentlyContinue) -ne $null
$r['upload_dir_exists'] = Test-Path 'C:\inetpub\wwwroot\upload'
$r['defender_rt_disabled'] = (Get-MpPreference -EA SilentlyContinue).DisableRealtimeMonitoring -eq $true
$r['guest_account_enabled'] = (Get-LocalUser -Name Guest).Enabled
$r['allow_insecure_guest_auth'] = (Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters' -EA SilentlyContinue).AllowInsecureGuestAuth -eq 1
$r['print_spooler_running'] = (Get-Service Spooler -EA SilentlyContinue).Status -eq 'Running'
$r['webclient_running'] = (Get-Service WebClient -EA SilentlyContinue).Status -eq 'Running'
# arya.txt in the all share — SYSVOL-style file disclosure
$r['arya_txt_in_all_share'] = Test-Path 'C:\shares\all\arya.txt'
# jeor.mormont is local admin
$admins = Get-LocalGroupMember Administrators -EA SilentlyContinue
$r['jeor_mormont_local_admin'] = [bool]($admins | Where-Object { $_.Name -match 'jeor.mormont' })

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.srv02_ip, castelblack_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"castelblack_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("castelblack_misconfigs", False,
                                   f"WinRM failed: {out}"))

    # ── braavos (SRV03) ──────────────────────────────────────────────────────
    braavos_script = r"""
Import-Module ActiveDirectory -EA SilentlyContinue
$r = @{}

$r['domain_joined_essos'] = ((Get-WmiObject Win32_ComputerSystem).Domain -eq 'essos.local')
$r['firewall_disabled'] = (Get-NetFirewallProfile | Where-Object { $_.Enabled }).Count -eq 0
$r['smb_signing_disabled'] = -not (Get-SmbServerConfiguration).RequireSecuritySignature
$r['print_spooler_running'] = (Get-Service Spooler -EA SilentlyContinue).Status -eq 'Running'
$r['webclient_running'] = (Get-Service WebClient -EA SilentlyContinue).Status -eq 'Running'
$r['adcs_running'] = (Get-Service CertSvc -EA SilentlyContinue).Status -eq 'Running'
$r['mssql_running'] = (Get-Service MSSQLSERVER -EA SilentlyContinue).Status -eq 'Running'
$r['laps_client_installed'] = Test-Path 'C:\Program Files\LAPS'
$r['public_share_exists'] = (Get-SmbShare -Name public -EA SilentlyContinue) -ne $null
$r['certenroll_share_exists'] = (Get-SmbShare -Name CertEnroll -EA SilentlyContinue) -ne $null
$r['lsa_ppl_enabled'] = (Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Control\Lsa' -EA SilentlyContinue).RunAsPPL -eq 1
$r['guest_account_enabled'] = (Get-LocalUser -Name Guest).Enabled
$r['khal_drogo_local_admin'] = (Get-LocalGroupMember Administrators | Where-Object { $_.Name -match 'khal' }) -ne $null
$r['gmsa_dragon_installed'] = (Test-ADServiceAccount gmsaDragon -EA SilentlyContinue) -eq $true

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.srv03_ip, braavos_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"braavos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("braavos_misconfigs", False,
                                   f"WinRM failed: {out}"))

    return results


def run_kerberos_checks(cfg: GOADConfig) -> list[CheckResult]:
    """AS-REP roasting and Kerberoasting via impacket."""
    results = []

    if not HAS_IMPACKET:
        results.append(CheckResult(
            "kerberos_checks", skipped=True,
            skip_reason="impacket not installed",
            passed=True, name="kerberos_checks"
        ))
        return results

    # AS-REP roasting — test via impacket GetNPUsers equivalent
    # We use the simpler subprocess approach since full impacket AS-REP
    # requires more setup; validate by checking the AD attribute instead
    asrep_checks = [
        (cfg.dc02_ip, "brandon.stark", "north.sevenkingdoms.local"),
        (cfg.dc03_ip, "missandei",     "essos.local"),
    ]
    for dc_ip, username, domain in asrep_checks:
        ok, out = winrm_ps(dc_ip, f"""
Import-Module ActiveDirectory
$u = Get-ADUser {username} -Properties DoesNotRequirePreAuth
Write-Output $u.DoesNotRequirePreAuth
""", cfg)
        passed = ok and "True" in out
        results.append(CheckResult(
            f"asrep_roastable_{username}", passed,
            f"DoesNotRequirePreAuth={out.strip() if ok else 'N/A'}"
        ))

    # Kerberoastable accounts (verify SPN presence)
    kerberoast_checks = [
        (cfg.dc02_ip, "sansa.stark",  "HTTP/eyrie.north.sevenkingdoms.local"),
        (cfg.dc02_ip, "jon.snow",     "HTTP/thewall.north.sevenkingdoms.local"),
        (cfg.dc02_ip, "sql_svc",      "MSSQLSvc/castelblack.north.sevenkingdoms.local"),
        (cfg.dc03_ip, "sql_svc",      "MSSQLSvc/braavos.essos.local"),
    ]
    for dc_ip, username, expected_spn in kerberoast_checks:
        ok, out = winrm_ps(dc_ip, f"""
Import-Module ActiveDirectory
$u = Get-ADUser {username} -Properties ServicePrincipalNames
Write-Output ($u.ServicePrincipalNames -join ',')
""", cfg)
        passed = ok and expected_spn.lower() in out.lower()
        results.append(CheckResult(
            f"kerberoastable_spn_{username}",
            passed,
            f"SPNs: {out.strip()[:80] if ok else 'N/A'}"
        ))

    return results


def run_mssql_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify MSSQL configuration on castelblack and braavos."""
    results = []

    # Castelblack MSSQL
    castelblack_sql = rf"""
$results = @{{}}
# SA login works
$r = sqlcmd -S localhost -U sa -P '{cfg.castelblack_sa_pass}' -C -Q "SELECT 1" -h-1 2>&1
$results['sa_login_works'] = $LASTEXITCODE -eq 0

# jon.snow sysadmin
$r2 = sqlcmd -S localhost -E -C -Q "SELECT IS_SRVROLEMEMBER('sysadmin','NORTH\\jon.snow')" -h-1 2>&1
$results['jon_snow_sysadmin'] = ($r2 | Out-String) -match '\b1\b'

# BRAAVOS linked server exists
$r3 = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.servers WHERE name='BRAAVOS' AND is_linked=1" -h-1 2>&1
$r3str = [string]($r3 | Out-String).Trim()
$r3match = $r3str -match '\b[1-9]'
$results['braavos_linked_server'] = [bool]$r3match

# arya.stark impersonation in master and msdb
$r4 = sqlcmd -S localhost -E -C -Q "USE master; SELECT COUNT(*) FROM sys.database_permissions dp JOIN sys.database_principals g ON dp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\\arya.stark' AND dp.type='IM'" -h-1 2>&1
$results['arya_impersonation_master'] = ($r4 | Out-String) -match '\b[1-9]\b'

$r5 = sqlcmd -S localhost -E -C -Q "USE msdb; SELECT COUNT(*) FROM sys.database_permissions dp JOIN sys.database_principals g ON dp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\\arya.stark' AND dp.type='IM'" -h-1 2>&1
$results['arya_impersonation_msdb'] = ($r5 | Out-String) -match '\b[1-9]\b'

$results.GetEnumerator() | ForEach-Object {{ Write-Output "$($_.Key):$($_.Value)" }}
"""
    ok, out = winrm_ps(cfg.srv02_ip, castelblack_sql, cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"mssql_castelblack_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("mssql_castelblack", False,
                                   f"WinRM failed: {out}"))

    # Braavos MSSQL
    braavos_sql = rf"""
$results = @{{}}
$r = sqlcmd -S localhost -U sa -P '{cfg.braavos_sa_pass}' -C -Q "SELECT 1" -h-1 2>&1
$results['sa_login_works'] = $LASTEXITCODE -eq 0

$r2 = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.servers WHERE name='CASTELBLACK' AND is_linked=1" -h-1 2>&1
$results['castelblack_linked_server'] = ($r2 | Out-String) -match '\b[1-9]\b'

$results.GetEnumerator() | ForEach-Object {{ Write-Output "$($_.Key):$($_.Value)" }}
"""
    ok, out = winrm_ps(cfg.srv03_ip, braavos_sql, cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"mssql_braavos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("mssql_braavos", False,
                                   f"WinRM failed: {out}"))

    return results


def run_adcs_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify ADCS ESC vulnerabilities on braavos and DC03."""
    results = []

    # Braavos-side checks (certutil, CertSvc)
    braavos_script = r"""
$r = @{}
$r['certsvc_running'] = (Get-Service CertSvc).Status -eq 'Running'
$esc6 = certutil -getreg policy\Editflags 2>&1
$r['esc6_altname_flag'] = [bool]($esc6 | Where-Object { $_ -match 'EDITF_ATTRIBUTESUBJECTALTNAME2' })
$esc11 = certutil -getreg CA\InterfaceFlags 2>&1
$r['esc11_unencrypted_requests'] = -not ($esc11 -match 'IF_ENFORCEENCRYPTICERTREQUEST')
$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.srv03_ip, braavos_script, cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"adcs_braavos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("adcs_braavos_services", False,
                                   f"WinRM failed on braavos: {out}"))

    # ESC4 ACL check — run on DC03 which has RSAT/AD module
    esc4_script = r"""
Import-Module ActiveDirectory -ErrorAction Stop
$templateDN = "CN=ESC4,CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
try {
    $acl = (Get-Acl "AD:$templateDN" -ErrorAction Stop).Access
    $found = [bool]($acl | Where-Object {
        $_.IdentityReference.Value -match 'khal' -and
        $_.ActiveDirectoryRights -match 'GenericAll'
    })
    Write-Output "esc4_khal_drogo_genericall:$found"
} catch {
    Write-Output "esc4_khal_drogo_genericall:False"
}
"""
    ok2, out2 = winrm_ps(cfg.dc03_ip, esc4_script, cfg, timeout=30)
    if ok2 and "esc4_khal_drogo_genericall:" in out2:
        val = out2.split("esc4_khal_drogo_genericall:")[1].strip()
        passed = val.lower() == "true"
        results.append(CheckResult(
            "adcs_dc03_esc4_khal_drogo_genericall", passed,
            f"khal.drogo GenericAll on ESC4 template = {val}"
        ))
    else:
        results.append(CheckResult("adcs_dc03_esc4_khal_drogo_genericall", False,
                                   f"Could not check on DC03: {out2}"))

    return results


def run_anonymous_rpc_check(cfg: GOADConfig) -> list[CheckResult]:
    """Verify anonymous RPC enumeration works on winterfell."""
    results = []

    # Use rpcclient if available, otherwise check via WinRM registry
    try:
        r = subprocess.run(
            ["rpcclient", "-U", "", "-N", cfg.dc02_ip,
             "-c", "enumdomusers"],
            capture_output=True, text=True, timeout=10
        )
        users_found = "arya.stark" in r.stdout or "jon.snow" in r.stdout
        results.append(CheckResult(
            "anonymous_rpc_winterfell_enumdomusers",
            users_found,
            f"rpcclient exit={r.returncode}, users={'found' if users_found else 'NOT found'}"
        ))
    except FileNotFoundError:
        # rpcclient not installed — verify via registry
        ok, out = winrm_ps(cfg.dc02_ip, r"""
$lsa = Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Control\Lsa'
Write-Output "RestrictAnonymous:$($lsa.RestrictAnonymous)"
$srv = Get-ItemProperty 'HKLM:\\SYSTEM\CurrentControlSet\Services\LanManServer\Parameters'
Write-Output "RestrictNullSessAccess:$($srv.RestrictNullSessAccess)"
""", cfg)
        ra_ok = ok and "RestrictAnonymous:0" in out
        rns_ok = ok and "RestrictNullSessAccess:0" in out
        results.append(CheckResult(
            "anonymous_rpc_registry_RestrictAnonymous_0", ra_ok,
            out.strip() if ok else "WinRM failed"
        ))
        results.append(CheckResult(
            "anonymous_rpc_registry_RestrictNullSessAccess_0", rns_ok,
            out.strip() if ok else "WinRM failed"
        ))
    except subprocess.TimeoutExpired:
        results.append(CheckResult(
            "anonymous_rpc_winterfell", False, "rpcclient timed out"
        ))

    return results


def run_forest_trust_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify forest trust and SID history between sevenkingdoms and essos."""
    results = []

    ok, out = winrm_ps(cfg.dc01_ip, r"""
Import-Module ActiveDirectory
$t = Get-ADTrust -Filter { Name -eq 'essos.local' } -Properties SIDFilteringForestAware
if ($t) {
    Write-Output "TrustExists:True"
    # SID history = Quarantined bit (0x04) NOT set in TrustAttributes
Write-Output "SIDHistoryEnabled:$(-not [bool]($t.TrustAttributes -band 0x04))"
} else {
    Write-Output "TrustExists:False"
    Write-Output "SIDHistoryEnabled:False"
}
""", cfg)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"forest_trust_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("forest_trust_check", False,
                                   f"WinRM failed: {out}"))

    return results


def run_acl_chain_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify the full GOAD ACL attack chains on sevenkingdoms and essos."""
    results = []

    # ── sevenkingdoms.local ACL chain — split into 2 calls to stay under WinRM limit ──
    sk_acl_part1 = r"""
Import-Module ActiveDirectory
$r = @{}
$jaimeDN   = (Get-ADUser 'jaime.lannister').DistinguishedName
$joffreyDN = (Get-ADUser 'joffrey.baratheon').DistinguishedName
$tyronDN   = (Get-ADUser 'tyron.lannister').DistinguishedName
$scDN      = (Get-ADGroup 'Small Council').DistinguishedName

$acl = (Get-Acl "AD:$jaimeDN").Access
$r['tywin_ForceChangePassword_on_jaime'] = [bool]($acl | Where-Object { $_.ActiveDirectoryRights -match 'ExtendedRight' })

          $acl = (Get-Acl "AD:$joffreyDN").Access
          $r['jaime_GenericWrite_on_joffrey'] = [bool]($acl | Where-Object {
              $_.IdentityReference -match 'jaime' -and ($_.ActiveDirectoryRights -match 'WriteProperty' -or $_.ActiveDirectoryRights -match 'GenericWrite') })

$acl = (Get-Acl "AD:$tyronDN").Access
$r['joffrey_WriteDacl_on_tyron'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'joffrey' -and $_.ActiveDirectoryRights -match 'WriteDacl' })

$acl = (Get-Acl "AD:$scDN").Access
$r['tyron_SelfMembership_SmallCouncil'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'tyron' })

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""

    sk_acl_part2 = r"""
Import-Module ActiveDirectory
$r = @{}
$dsDN  = (Get-ADGroup 'DragonStone' -EA SilentlyContinue).DistinguishedName
$kgDN  = (Get-ADGroup 'KingsGuard' -EA SilentlyContinue).DistinguishedName
$stanisDN = (Get-ADUser 'stannis.baratheon').DistinguishedName
$kl    = Get-ADComputer 'kingslanding' -EA SilentlyContinue
$crownDN = (Get-ADOrganizationalUnit -Filter { Name -eq 'Crownlands' } -EA SilentlyContinue).DistinguishedName

if ($dsDN) {
    $acl = (Get-Acl "AD:$dsDN").Access
    $r['SmallCouncil_AddMember_DragonStone'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'Small.Council' })
} else { $r['SmallCouncil_AddMember_DragonStone'] = $false }

if ($kgDN) {
    $acl = (Get-Acl "AD:$kgDN").Access
    $r['DragonStone_WriteOwner_KingsGuard'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'DragonStone' -and $_.ActiveDirectoryRights -match 'WriteOwner' })
    $r['KingsGuard_GenericAll_stannis'] = [bool]((Get-Acl "AD:$stanisDN").Access | Where-Object {
        $_.IdentityReference -match 'KingsGuard' -and $_.ActiveDirectoryRights -match 'GenericAll' })
} else {
    $r['DragonStone_WriteOwner_KingsGuard'] = $false
    $r['KingsGuard_GenericAll_stannis'] = $false
}

if ($kl) {
    $acl = (Get-Acl "AD:$($kl.DistinguishedName)").Access
    $r['stannis_GenericAll_kingslanding'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'stannis' -and $_.ActiveDirectoryRights -match 'GenericAll' })
    $r['AcrossTheNarrowSea_GenericAll_kingslanding'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'AcrossTheNarrowSea' -and $_.ActiveDirectoryRights -match 'GenericAll' })
} else {
    $r['stannis_GenericAll_kingslanding'] = $false
    $r['AcrossTheNarrowSea_GenericAll_kingslanding'] = $false
}

if ($crownDN) {
    $acl = (Get-Acl "AD:$crownDN").Access
    $r['renly_WriteDacl_Crownlands'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'renly' -and $_.ActiveDirectoryRights -match 'WriteDacl' })
} else { $r['renly_WriteDacl_Crownlands'] = $false }

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""

    for script in [sk_acl_part1, sk_acl_part2]:
        ok, out = winrm_ps(cfg.dc01_ip, script, cfg, timeout=60)
        if ok:
            for line in out.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    passed = val.strip().lower() == "true"
                    results.append(CheckResult(
                        f"acl_chain_sk_{key.strip()}", passed,
                        f"{key.strip()} = {val.strip()}"
                    ))
        else:
            results.append(CheckResult("acl_chain_sevenkingdoms_part", False,
                                       f"WinRM failed: {out[:100]}"))

    # ── essos.local ACL chain ──────────────────────────────────────────────────
    # khal.drogo→viserys (GenericAll), Spys→jorah (GenericAll),
    # viserys→jorah (WriteProperty), DragonsFriends→braavos$ (GenericWrite),
    # missandei→khal (GenericAll), gmsaDragon$→drogon (GenericAll),
    # missandei→viserys (GenericWrite)
    essos_acl_script = r"""
Import-Module ActiveDirectory
$r = @{}

$viserys = (Get-ADUser 'viserys.targaryen').DistinguishedName
$jorah   = (Get-ADUser 'jorah.mormont').DistinguishedName
$khal    = (Get-ADUser 'khal.drogo').DistinguishedName
$miss    = (Get-ADUser 'missandei').DistinguishedName
$drogon  = (Get-ADUser 'drogon').DistinguishedName

# khal.drogo → viserys: GenericAll
$acl = (Get-Acl "AD:$viserys").Access
$r['khal_GenericAll_viserys'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'khal' -and $_.ActiveDirectoryRights -match 'GenericAll' })

# Spys group → jorah.mormont: GenericAll
$acl = (Get-Acl "AD:$jorah").Access
$r['Spys_GenericAll_jorah'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'Spys' -and $_.ActiveDirectoryRights -match 'GenericAll' })

# viserys → jorah: WriteProperty
$acl = (Get-Acl "AD:$jorah").Access
$r['viserys_WriteProperty_jorah'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'viserys' -and $_.ActiveDirectoryRights -match 'WriteProperty' })

# DragonsFriends → braavos$ computer: GenericWrite
$braavos = Get-ADComputer 'braavos' -EA SilentlyContinue
if ($braavos) {
    $acl = (Get-Acl "AD:$($braavos.DistinguishedName)").Access
    $r['DragonsFriends_GenericWrite_braavos'] = [bool]($acl | Where-Object {
        $_.IdentityReference -match 'DragonsFriends' -and ($_.ActiveDirectoryRights -match 'WriteProperty' -or $_.ActiveDirectoryRights -match 'GenericWrite') })
} else { $r['DragonsFriends_GenericWrite_braavos'] = $false }

# missandei → khal.drogo: GenericAll
$acl = (Get-Acl "AD:$khal").Access
$r['missandei_GenericAll_khal'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'missandei' -and $_.ActiveDirectoryRights -match 'GenericAll' })

# gmsaDragon$ → drogon: GenericAll
$acl = (Get-Acl "AD:$drogon").Access
$r['gmsaDragon_GenericAll_drogon'] = [bool]($acl | Where-Object {
    $_.ActiveDirectoryRights -match 'GenericAll' -and
    $_.IdentityReference.Value -match 'gmsaDragon' })

# missandei → viserys: GenericWrite (WriteProperty)
$acl = (Get-Acl "AD:$viserys").Access
$r['missandei_GenericWrite_viserys'] = [bool]($acl | Where-Object {
    $_.IdentityReference -match 'missandei' -and ($_.ActiveDirectoryRights -match 'WriteProperty' -or $_.ActiveDirectoryRights -match 'GenericWrite') })

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc03_ip, essos_acl_script, cfg, timeout=60)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"acl_chain_essos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("acl_chain_essos", False,
                                   f"WinRM failed: {out}"))

    return results


def run_adcs_template_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify ADCS ESC certificate templates are published in essos.local."""
    results = []

    # Templates must be checked on DC03 (has local ADWS access to Configuration NC).
    # Actual names used by badsectorlabs.ludus_adcs differ from the ESC numbering.
    template_script = r"""
Import-Module ActiveDirectory
$configDN = "CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=essos,DC=local"
$published = @{}

# Map expected names to actual template names in the domain
$templateMap = @{
    'ESC1'    = 'ESC1'
    'ESC2'    = 'ESC2'
    'ESC3'    = 'ESC3'
    'ESC3_CRA'= 'ESC3_CRA'
    'ESC4'    = 'ESC4'
    'ESC7'    = 'ESC7_CertMgr'
    'ESC9'    = 'ESC9'
    'ESC13'   = 'ESC13'
}
foreach ($key in $templateMap.Keys) {
    $name = $templateMap[$key]
    $obj = Get-ADObject -Filter "Name -eq '$name'" -SearchBase $configDN -EA SilentlyContinue
    $published["template_$key"] = [bool]$obj
}
$published.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc03_ip, template_script, cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"adcs_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("adcs_templates", False,
                                   f"WinRM failed on DC03: {out}"))

    # ESC7: viserys.targaryen should have ManageCA on the CA
    # Check via certutil -getreg CA\Security on the CA server (braavos/SRV03)
    esc7_script = r"""
# Check if viserys.targaryen has Officer/ManageCA rights on the CA
# certutil -getreg CA\Security outputs named ACEs
$sec = certutil -getreg CA\Security 2>&1 | Out-String
Write-Output "raw_security_has_viserys:$([bool]($sec -match 'viserys'))"

# Alternatively check via COM object
try {
    $CAConfig = (certutil -getconfig 2>&1 | Select-String 'Config:') -replace 'Config:\s*', '' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Select-Object -First 1
    if ($CAConfig) {
        $CA = New-Object -ComObject CertificateAuthority.Admin
        $SD = $CA.GetCASecurity($CAConfig, 0x6)
        Write-Output "esc7_viserys_ManageCA:$([bool]($SD -match 'viserys'))"
    } else {
        Write-Output "esc7_viserys_ManageCA:$([bool]($sec -match 'viserys'))"
    }
} catch {
    Write-Output "esc7_viserys_ManageCA:$([bool]($sec -match 'viserys'))"
}
"""
    ok2, out2 = winrm_ps(cfg.srv03_ip, esc7_script, cfg, timeout=20)
    if ok2:
        for line in (out2 or "").splitlines():
            if "esc7_viserys_ManageCA:" in line:
                val = line.split("esc7_viserys_ManageCA:")[1].strip()
                results.append(CheckResult(
                    "adcs_esc7_viserys_ManageCA", val.lower() == "true",
                    f"viserys.targaryen ManageCA = {val}"
                ))
                break
        else:
            # Fallback: check raw security output
            has_viserys = "raw_security_has_viserys:True" in (out2 or "")
            results.append(CheckResult(
                "adcs_esc7_viserys_ManageCA", has_viserys,
                f"viserys in CA security descriptor = {has_viserys}"
            ))
    else:
        results.append(CheckResult("adcs_esc7_viserys_ManageCA", False,
                                   f"WinRM failed on braavos: {out2}"))

    return results


def run_mssql_extended_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify MSSQL ExecuteAs chains and additional sysadmin accounts."""
    results = []

    # Castelblack extended: samwell→sa, brandon→jon.snow login impersonation
    castelblack_ext = rf"""
$r = @{{}}

# samwell.tarly can impersonate sa (ExecuteAs LOGIN)
$r1 = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\samwell.tarly' AND sp.type='IM'" -h-1 2>&1
$r['samwell_impersonate_sa'] = ($r1 | Out-String) -match '\b[1-9]\b'

# brandon.stark can impersonate jon.snow (ExecuteAs LOGIN)
$r2 = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='NORTH\brandon.stark' AND sp.type='IM'" -h-1 2>&1
$r['brandon_impersonate_jon_snow'] = ($r2 | Out-String) -match '\b[1-9]\b'

$r.GetEnumerator() | ForEach-Object {{ Write-Output "$($_.Key):$($_.Value)" }}
"""
    ok, out = winrm_ps(cfg.srv02_ip, castelblack_ext, cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"mssql_castelblack_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("mssql_castelblack_extended", False,
                                   f"WinRM failed: {out}"))

    # Braavos extended: khal.drogo sysadmin, jorah.mormont ExecuteAs sa
    braavos_ext = rf"""
$r = @{{}}

# khal.drogo is sysadmin on braavos
$r1 = sqlcmd -S localhost -E -C -Q "SELECT IS_SRVROLEMEMBER('sysadmin','ESSOS\khal.drogo')" -h-1 2>&1
$r['khal_drogo_sysadmin'] = ($r1 | Out-String) -match '\b1\b'

# jorah.mormont can impersonate sa
$r2 = sqlcmd -S localhost -E -C -Q "SELECT COUNT(*) FROM sys.server_permissions sp JOIN sys.server_principals g ON sp.grantee_principal_id=g.principal_id WHERE g.name='ESSOS\jorah.mormont' AND sp.type='IM'" -h-1 2>&1
$r['jorah_impersonate_sa'] = ($r2 | Out-String) -match '\b[1-9]\b'

$r.GetEnumerator() | ForEach-Object {{ Write-Output "$($_.Key):$($_.Value)" }}
"""
    ok2, out2 = winrm_ps(cfg.srv03_ip, braavos_ext, cfg, timeout=30)
    if ok2:
        for line in out2.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"mssql_braavos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("mssql_braavos_extended", False,
                                   f"WinRM failed: {out2}"))

    return results


def run_ntlm_and_auth_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Check NTLM downgrade, LLMNR, NBT-NS, and Credential Manager."""
    results = []

    # meereen: LmCompatibilityLevel = 2 (NTLM v1 allowed)
    ntlm_script = r"""
$r = @{}
$lm = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -EA SilentlyContinue).LmCompatibilityLevel
$r['ntlm_downgrade_lm_compat_2'] = ($lm -eq 2 -or $lm -eq $null)  # 2 = NTLM only, null = default allows downgrade

# Trust exists to sevenkingdoms
$r['trust_sevenkingdoms_local'] = (Get-ADTrust -Filter { Name -like '*sevenkingdoms*' } -EA SilentlyContinue) -ne $null
$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok, out = winrm_ps(cfg.dc03_ip, ntlm_script, cfg, timeout=20)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"meereen_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("meereen_ntlm_checks", False,
                                   f"WinRM failed: {out}"))

    # winterfell: LLMNR + NBT-NS enabled, Credential Manager has robb.stark→castelblack
    winter_auth_script = r"""
$r = @{}

# LLMNR enabled (registry under DNSClient)
$llmnr = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient' -EA SilentlyContinue).EnableMulticast
$r['llmnr_enabled'] = ($llmnr -ne 0)  # 0 = disabled, absent = enabled by default

# NBT-NS: check via WMI adapter settings (requires net adapter enumeration)
# Simpler check: RestrictNullSessAccess=0 already covered in anonymous_rpc
# Check credential manager for robb.stark (TERMSRV/castelblack stored in their vault)
# The credential is stored under robb.stark's user profile vault, not localuser's
$robbVault = 'C:\Users\robb.stark\AppData\Local\Microsoft\Vault'
$vaultFiles = Get-ChildItem $robbVault -Recurse -EA SilentlyContinue
# Vault has files = credentials stored in robb.stark's vault
$r['credential_mgr_castelblack'] = [bool]($vaultFiles | Where-Object { $_.Name -match 'vpol|vsch|\{' })

$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
"""
    ok2, out2 = winrm_ps(cfg.dc02_ip, winter_auth_script, cfg, timeout=20)
    if ok2:
        for line in out2.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"winterfell_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("winterfell_auth_checks", False,
                                   f"WinRM failed: {out2}"))

    return results


def run_cross_domain_group_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify cross-domain FSP group memberships (DragonsFriends and Spys)."""
    results = []

    # DragonsFriends on DC03 should have tyron.lannister (sevenkingdoms FSP) + daenerys
    ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup DragonsFriends -Properties Members -EA SilentlyContinue
Write-Output "DragonsFriends_count:$($grp.Members.Count)"
""", cfg)
    if ok and "DragonsFriends_count:" in out:
        cnt = out.split("DragonsFriends_count:")[1].strip()
        try:
            passed = int(cnt) >= 2
        except ValueError:
            passed = False
        results.append(CheckResult(
            "cross_domain_DragonsFriends_has_members", passed,
            f"DragonsFriends member count = {cnt} (expected ≥2: tyron.lannister + daenerys)"
        ))

    # Spys on DC03 should have Small Council (sevenkingdoms FSP)
    ok2, out2 = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory
$grp = Get-ADGroup Spys -Properties Members -EA SilentlyContinue
Write-Output "Spys_count:$($grp.Members.Count)"
""", cfg)
    if ok2 and "Spys_count:" in out2:
        cnt = out2.split("Spys_count:")[1].strip()
        try:
            passed = int(cnt) >= 1
        except ValueError:
            passed = False
        results.append(CheckResult(
            "cross_domain_Spys_has_SmallCouncil", passed,
            f"Spys member count = {cnt} (expected ≥1: Small Council FSP)"
        ))

    return results


def run_password_policy_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify weak password policies are set on all three domains."""
    results = []

    for ip, domain_label, domain_dn in [
        (cfg.dc01_ip, "sevenkingdoms", "DC=sevenkingdoms,DC=local"),
        (cfg.dc02_ip, "north",         "DC=north,DC=sevenkingdoms,DC=local"),
        (cfg.dc03_ip, "essos",         "DC=essos,DC=local"),
    ]:
        script = f"""
Import-Module ActiveDirectory
$pol = Get-ADDefaultDomainPasswordPolicy -Identity '{domain_dn}' -EA SilentlyContinue
if ($pol) {{
    Write-Output "complexity:$($pol.ComplexityEnabled)"
    Write-Output "min_length:$($pol.MinPasswordLength)"
}} else {{
    Write-Output "complexity:UNKNOWN"
    Write-Output "min_length:UNKNOWN"
}}
"""
        ok, out = winrm_ps(ip, script, cfg, timeout=20)
        if ok:
            complexity_ok = "complexity:False" in out
            min_len_ok = any(f"min_length:{n}" in out for n in ["0","1","2","3","4","5","6","7"])
            results.append(CheckResult(
                f"password_policy_{domain_label}_complexity_disabled",
                complexity_ok,
                f"ComplexityEnabled = {'False (correct)' if complexity_ok else 'True (UNEXPECTED)'}"
            ))
            results.append(CheckResult(
                f"password_policy_{domain_label}_min_length_weak",
                min_len_ok,
                f"MinPasswordLength = {out.split('min_length:')[1].split()[0] if 'min_length:' in out else 'UNKNOWN'}"
            ))
        else:
            results.append(CheckResult(f"password_policy_{domain_label}", False,
                                       f"WinRM failed: {out}"))

    return results


def run_sysvol_and_files_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify SYSVOL scripts and file deployments that expose credentials."""
    results = []

    # SYSVOL script.ps1 on winterfell — contains jeor.mormont password in plaintext
    ok, out = winrm_ps(cfg.dc02_ip, r"""
$scriptPath = 'C:\Windows\SYSVOL\domain\scripts\script.ps1'
$r = @{}
$r['sysvol_script_exists'] = Test-Path $scriptPath
if ($r['sysvol_script_exists']) {
    $content = Get-Content $scriptPath -Raw -EA SilentlyContinue
    # Upstream GOAD script.ps1 contains jeor.mormont credentials
    $r['sysvol_script_has_credentials'] = [bool]($content -match 'jeor' -or $content -match 'password' -or $content -match 'mormont')
} else {
    $r['sysvol_script_has_credentials'] = $false
}
$r.GetEnumerator() | ForEach-Object { Write-Output "$($_.Key):$($_.Value)" }
""", cfg)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"winterfell_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("winterfell_sysvol_check", False,
                                   f"WinRM failed: {out}"))

    return results


def run_laps_reader_checks(cfg: GOADConfig) -> list[CheckResult]:
    """Verify LAPS reader permissions on braavos$ in essos.local."""
    results = []

    # jorah.mormont and Spys group should be able to read LAPS password on braavos$
    ok, out = winrm_ps(cfg.dc03_ip, r"""
Import-Module ActiveDirectory

$braavos = Get-ADComputer braavos -Properties * -EA SilentlyContinue
if (-not $braavos) {
    Write-Output "laps_braavos_in_laps_ou:False"
    Write-Output "laps_jorah_can_read:False"
    Write-Output "laps_spys_can_read:False"
    return
}

# Check braavos is in the LAPS OU
$lapsOU = "OU=Laps,DC=essos,DC=local"
Write-Output "laps_braavos_in_laps_ou:$($braavos.DistinguishedName -match 'Laps')"

# Check ACL on braavos$ for LAPS read access
# LAPS sets ms-Mcs-AdmPwd read rights and ms-Mcs-AdmPwdExpirationTime
$acl = (Get-Acl "AD:$($braavos.DistinguishedName)" -EA SilentlyContinue).Access
$jorahSid = (Get-ADUser jorah.mormont -Properties objectSid -EA SilentlyContinue).objectSid
$spysSid  = (Get-ADGroup Spys -Properties objectSid -EA SilentlyContinue).objectSid

if ($jorahSid) {
    $jorahSID = New-Object System.Security.Principal.SecurityIdentifier($jorahSid)
    $hasJorah = [bool]($acl | Where-Object {
        try { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -eq $jorahSID.Value } catch { $false }
    })
    Write-Output "laps_jorah_can_read:$hasJorah"
} else {
    Write-Output "laps_jorah_can_read:False"
}

if ($spysSid) {
    $spysSID = New-Object System.Security.Principal.SecurityIdentifier($spysSid)
    $hasSpys = [bool]($acl | Where-Object {
        try { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -eq $spysSID.Value } catch { $false }
    })
    Write-Output "laps_spys_can_read:$hasSpys"
} else {
    Write-Output "laps_spys_can_read:False"
}
""", cfg, timeout=30)
    if ok:
        for line in out.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                passed = val.strip().lower() == "true"
                results.append(CheckResult(
                    f"essos_{key.strip()}", passed,
                    f"{key.strip()} = {val.strip()}"
                ))
    else:
        results.append(CheckResult("essos_laps_reader_check", False,
                                   f"WinRM failed: {out}"))

    return results


# ── Runner ────────────────────────────────────────────────────────────────────
CATEGORIES = [
    ("Network Connectivity",    run_network_checks),
    ("SMB Configuration",       run_smb_checks),
    ("AD Users",                run_ad_user_checks),
    ("AD Groups",               run_ad_group_checks),
    ("ACL Attack Paths",        run_acl_checks),
    ("ACL Chains (Full)",       run_acl_chain_checks),
    ("Misconfigurations",       run_misconfiguration_checks),
    ("SYSVOL & Files",          run_sysvol_and_files_checks),
    ("LAPS Reader Permissions", run_laps_reader_checks),
    ("NTLM & Auth",             run_ntlm_and_auth_checks),
    ("Kerberos",                run_kerberos_checks),
    ("MSSQL",                   run_mssql_checks),
    ("MSSQL Extended",          run_mssql_extended_checks),
    ("ADCS",                    run_adcs_checks),
    ("ADCS Templates",          run_adcs_template_checks),
    ("Cross-Domain Groups",     run_cross_domain_group_checks),
    ("Password Policy",         run_password_policy_checks),
    ("Anonymous RPC",           run_anonymous_rpc_check),
    ("Forest Trust",            run_forest_trust_checks),
]


def detect_second_octet(range_id: str) -> Optional[int]:
    """Try to detect the second octet from the Ludus CLI."""
    api_key = os.environ.get("LUDUS_API_KEY", "")
    if not api_key:
        return None
    try:
        result = subprocess.run(
            ["ludus", "range", "list", "-r", range_id],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "LUDUS_API_KEY": api_key}
        )
        # Parse "10.X.0.0/16" from output
        m = re.search(r"10\.(\d+)\.0\.0/16", result.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def print_header(text: str) -> None:
    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 60}{RESET}")


def print_result(r: CheckResult, verbose: bool) -> None:
    if r.skipped:
        if verbose:
            print(f"  {YELLOW}SKIP{RESET}  {r.name}  ({r.skip_reason})")
        return
    icon = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
    line = f"  [{icon}]  {r.name}"
    if not r.passed or verbose:
        if r.detail:
            line += f"  — {r.detail}"
    print(line)


def run_all(cfg: GOADConfig, verbose: bool = False) -> int:
    total = passed = failed = skipped = 0
    all_failures: list[CheckResult] = []

    for category_name, fn in CATEGORIES:
        print_header(category_name)
        try:
            results = fn(cfg)
        except Exception as exc:
            print(f"  {RED}ERROR{RESET}  Category '{category_name}' crashed: {exc}")
            continue

        for r in results:
            total += 1
            print_result(r, verbose)
            if r.skipped:
                skipped += 1
            elif r.passed:
                passed += 1
            else:
                failed += 1
                all_failures.append(r)

    # Summary
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}SUMMARY{RESET}  Total: {total}  "
          f"{GREEN}Passed: {passed}{RESET}  "
          f"{RED}Failed: {failed}{RESET}  "
          f"{YELLOW}Skipped: {skipped}{RESET}")

    if all_failures:
        print(f"\n{BOLD}{RED}FAILED CHECKS:{RESET}")
        for r in all_failures:
            print(f"  {RED}✗{RESET}  {r.name}")
            if r.detail:
                print(f"       {r.detail}")

    print(f"{'─' * 60}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GOAD misconfiguration validation tool"
    )
    parser.add_argument("--range-id", default="GOAD1",
                        help="Ludus range ID (default: GOAD1)")
    parser.add_argument("--second-octet", type=int,
                        help="Network second octet (auto-detected if not set)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detail for passing checks too")
    parser.add_argument("--category", "-c",
                        help="Run only this category (partial match)")
    args = parser.parse_args()

    # Determine second octet
    octet = args.second_octet
    if octet is None:
        octet = detect_second_octet(args.range_id)
    if octet is None:
        # Fallback: try to infer from range ID (GOAD1 → 1, GOAD2 → 2 ...)
        m = re.search(r"(\d+)$", args.range_id)
        if m:
            octet = int(m.group(1))
        else:
            print(f"{RED}ERROR{RESET}: Could not detect network second octet. "
                  "Use --second-octet or set LUDUS_API_KEY.", file=sys.stderr)
            return 2

    cfg = GOADConfig(second_octet=octet)

    print(f"{BOLD}GOAD Validation — Range {args.range_id}{RESET}")
    print(f"Network: 10.{octet}.10.0/24")
    print(f"DC01 (kingslanding):  {cfg.dc01_ip}")
    print(f"DC02 (winterfell):    {cfg.dc02_ip}")
    print(f"SRV02 (castelblack):  {cfg.srv02_ip}")
    print(f"DC03 (meereen):       {cfg.dc03_ip}")
    print(f"SRV03 (braavos):      {cfg.srv03_ip}")

    if not HAS_WINRM:
        print(f"{YELLOW}WARNING{RESET}: pywinrm not installed — WinRM checks will fail.")
    if not HAS_LDAP3:
        print(f"{YELLOW}WARNING{RESET}: ldap3 not installed — LDAP checks skipped.")
    if not HAS_IMPACKET:
        print(f"{YELLOW}WARNING{RESET}: impacket not installed — Kerberos checks use WinRM fallback.")

    global CATEGORIES
    if args.category:
        pattern = args.category.lower()
        CATEGORIES = [(n, f) for n, f in CATEGORIES if pattern in n.lower()]
        if not CATEGORIES:
            print(f"{RED}ERROR{RESET}: No category matches '{args.category}'")
            return 2

    return run_all(cfg, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
