#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) Bad Sector Labs — https://github.com/badsectorlabs/ludus-range-configs
"""Validate the manifests in this Ludus source.

A Ludus source can ship any combination of Packer templates, Ansible roles,
and blueprints. This script checks whatever is present:

  - source.yml       (optional file)   -- manifest_version required if present
  - blueprints/<id>/blueprint.yml      -- required fields when the dir exists
  - blueprints/<id>/<config>           -- referenced by blueprint.yml.config

A source with only ansible/roles/, ansible/collections/, or templates/ is
valid and exits clean. Those ansible/ entries may be git submodules (pinned
to release tags) that are not checked out in CI; their presence still counts
as shipping content. An empty source is rejected.

Add your own checks below.
"""
import os
import re
import sys
import yaml

ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_\-]*(/[A-Za-z0-9_\-]+){0,2}$')
# manifest_version is optional (Ludus defaults it to 1); it is only required
# once a future breaking schema bumps it, so it is not in any required set.
BLUEPRINT_REQUIRED = {"id", "name", "description", "version", "config"}
SOURCE_REQUIRED = set()


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def validate_source_yml(fail):
    if not os.path.isfile("source.yml"):
        return fail
    try:
        m = load_yaml("source.yml")
    except yaml.YAMLError as e:
        print(f"::error::source.yml invalid YAML: {e}")
        return True
    missing = SOURCE_REQUIRED - m.keys()
    if missing:
        print(f"::error::source.yml missing fields: {sorted(missing)}")
        fail = True
    return fail


def validate_blueprint(d, fail):
    manifest = f"blueprints/{d}/blueprint.yml"
    if not os.path.isfile(manifest):
        print(f"::error::{manifest} missing")
        return True
    try:
        m = load_yaml(manifest)
    except yaml.YAMLError as e:
        print(f"::error::{manifest} invalid YAML: {e}")
        return True
    missing = BLUEPRINT_REQUIRED - m.keys()
    if missing:
        print(f"::error::{manifest} missing fields: {sorted(missing)}")
        fail = True
    if "id" in m and not ID_RE.match(str(m["id"])):
        print(f"::error::{manifest} invalid id: {m['id']!r}")
        fail = True
    cfg = f"blueprints/{d}/{m.get('config', 'range-config.yml')}"
    if not os.path.isfile(cfg):
        print(f"::error::{cfg} missing")
        return True
    try:
        load_yaml(cfg)
    except yaml.YAMLError as e:
        print(f"::error::{cfg} invalid YAML: {e}")
        fail = True
    return fail


def main() -> int:
    fail = False
    fail = validate_source_yml(fail)

    has_blueprints = os.path.isdir("blueprints") and any(
        os.path.isdir(f"blueprints/{d}") for d in os.listdir("blueprints")
    )
    # Roles live under ansible/roles/, collections under
    # ansible/collections/. Each entry may be a git submodule that is NOT
    # checked out in CI (validate.yml / .gitlab-ci.yml don't recurse
    # submodules), so an entry is "shipped" if its name is present under the
    # parent dir even when the gitlink directory is empty. listdir lists
    # gitlink dir names regardless of whether their content is materialized.
    has_roles = os.path.isdir("ansible/roles") and bool(os.listdir("ansible/roles"))
    has_collections = os.path.isdir("ansible/collections") and bool(
        os.listdir("ansible/collections")
    )
    has_templates = os.path.isdir("templates") and any(
        os.path.isdir(f"templates/{d}") for d in os.listdir("templates")
    )

    if not (has_blueprints or has_roles or has_collections or has_templates):
        print("::error::source ships nothing; populate at least one of blueprints/, ansible/roles/, ansible/collections/, or templates/")
        return 1

    if has_blueprints:
        for d in sorted(os.listdir("blueprints")):
            if os.path.isdir(f"blueprints/{d}"):
                fail = validate_blueprint(d, fail)

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
