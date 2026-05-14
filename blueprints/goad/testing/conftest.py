# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) Bad Sector Labs — https://github.com/badsectorlabs/ludus-range-configs
"""
conftest.py — shared pytest configuration for GOAD tests.
Handles CLI option registration and auto-detection of range settings.
"""
import os
import re
import subprocess
import pytest
from validate_goad import GOADConfig, detect_second_octet


def pytest_addoption(parser):
    parser.addoption(
        "--second-octet", type=int, default=None,
        help="Network second octet (e.g. 1 for 10.1.x.x). Auto-detected from Ludus if not set."
    )
    parser.addoption(
        "--range-id", default=None,
        help="Ludus range ID (e.g. GOAD1). Used for auto-detection."
    )


@pytest.fixture(scope="session")
def cfg(request) -> GOADConfig:
    """Session-scoped GOADConfig — built once, shared across all tests."""
    octet = request.config.getoption("--second-octet")
    range_id = request.config.getoption("--range-id")

    # Priority: CLI arg > env var > auto-detect from Ludus > infer from range ID
    if octet is None:
        octet_env = os.environ.get("GOAD_SECOND_OCTET")
        if octet_env:
            octet = int(octet_env)

    if range_id is None:
        range_id = os.environ.get("GOAD_RANGE_ID", "GOAD1")

    if octet is None:
        octet = detect_second_octet(range_id)

    if octet is None:
        m = re.search(r"(\d+)$", range_id)
        octet = int(m.group(1)) if m else 1

    print(f"\n[GOAD] Range: {range_id}  Network: 10.{octet}.10.0/24")
    return GOADConfig(second_octet=octet)
