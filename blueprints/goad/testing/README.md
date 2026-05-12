# GOAD Testing Framework

Validation scripts for the GOAD (Game of Active Directory) Ludus range.
Runs from the Ludus server which has direct network access to all VMs.

## Files

| File | Purpose |
|------|---------|
| `validate_goad.py` | Standalone validation script — human-readable output |
| `test_goad.py` | Pytest test suite — same checks as individual test cases |
| `conftest.py` | Pytest configuration and shared fixtures |

## Requirements

```bash
pip3 install pytest pywinrm ldap3 impacket
# smbclient for SMB share checks (optional, usually pre-installed)
```

## Usage

### Standalone script (human-readable)

```bash
# Auto-detect range from Ludus CLI
export LUDUS_API_KEY='your-api-key'
python3 validate_goad.py --range-id GOAD1

# Explicit second octet
python3 validate_goad.py --second-octet 1

# Verbose (show passing checks too)
python3 validate_goad.py --second-octet 1 --verbose

# Run only one category
python3 validate_goad.py --second-octet 1 --category mssql
```

### Pytest (CI-friendly, per-check pass/fail)

```bash
# All tests
pytest test_goad.py -v --second-octet=1

# Specific class
pytest test_goad.py -v -k "winterfell"

# Specific test
pytest test_goad.py -v -k "test_asrep_brandon_stark"

# Short output
pytest test_goad.py --second-octet=1 --tb=short

# With different range
pytest test_goad.py -v --range-id=GOAD2

# Using environment variables
GOAD_SECOND_OCTET=1 pytest test_goad.py -v
```

## Test Categories

| Category | What it checks |
|----------|---------------|
| `TestNetwork` | TCP reachability of all VMs on key ports |
| `TestSMB` | SMB signing disabled, correct shares on castelblack/braavos |
| `TestADUsers` | All GOAD users exist, password in samwell description |
| `TestADGroups` | Group memberships, nested DA chain, cross-domain FSPs |
| `TestACLPaths` | Key ACE attack paths (varys, khal, gmsaDragon) |
| `TestWinterfellMisconfigs` | Firewall, autologon, AS-REP, delegation, scheduled tasks, GPO |
| `TestKingslandingMisconfigs` | ESC10 KDC registry, Defender GPO, AccountNotDelegated |
| `TestMeereenMisconfigs` | AS-REP missandei, LAPS OU, gMSA, Defender GPO |
| `TestCastelblackMisconfigs` | Domain join, IIS, MSSQL, Defender disabled, guest |
| `TestBraavosServices` | ADCS, MSSQL, LAPS OU, LSA PPL, khal.drogo local admin |
| `TestKerberos` | SPNs for kerberoastable accounts, AS-REP flags |
| `TestMSSQL` | SA login, sysadmins, linked servers, impersonation |
| `TestADCS` | ESC6, ESC11 flags, CertSvc running |
| `TestForestTrust` | Trust exists, SID history enabled |

## Exit Codes

- `validate_goad.py`: `0` = all pass, `1` = failures, `2` = configuration error
- `pytest`: standard pytest exit codes (`0` pass, `1` failures)
