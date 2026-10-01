#!/bin/sh
set -eu

# Keep Focal's system Python 3.8; Ansible-core 2.21 needs Python >= 3.9.
python_version=3.11.16
python_build=20260924
python_sha256=68c6739376b65258dee5058ccf6777232fe38d31a578965ae8bda327ec7da3a8
python_prefix=/opt/ludus/python3.11
# This binding release supports Focal's libapt-pkg 6.0 and Python 3.11.
python_apt_version=2.2.1
python_apt_sha256=b9336cc92dc0a3bcc7be05b40f6752d10220cc968b19061f6c7fc12bf22a97f2

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl g++ libapt-pkg-dev xz-utils

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
archive="cpython-${python_version}+${python_build}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
curl --fail --location --silent --show-error \
    "https://github.com/astral-sh/python-build-standalone/releases/download/${python_build}/${archive}" \
    --output "$workdir/python.tar.gz"
printf '%s  %s\n' "$python_sha256" "$workdir/python.tar.gz" | sha256sum --check -
mkdir -p "$python_prefix"
tar -xzf "$workdir/python.tar.gz" --strip-components=1 -C "$python_prefix"

# Distro python3-apt is compiled for Python 3.8, not the private interpreter.
curl --fail --location --silent --show-error \
    "https://archive.debian.org/debian/pool/main/p/python-apt/python-apt_${python_apt_version}.tar.xz" \
    --output "$workdir/python-apt.tar.xz"
printf '%s  %s\n' "$python_apt_sha256" "$workdir/python-apt.tar.xz" | sha256sum --check -
tar -xJf "$workdir/python-apt.tar.xz" -C "$workdir"
"$python_prefix/bin/python3.11" -m ensurepip
(
    cd "$workdir/python-apt-${python_apt_version}"
    CC=gcc CXX=g++ LDSHARED='g++ -shared' DEBVER="$python_apt_version" \
        "$python_prefix/bin/python3.11" setup.py build --parallel=2 install
)

"$python_prefix/bin/python3.11" - <<'PYTHON'
import apt
import apt_inst
import apt_pkg

assert apt_pkg.version_compare("1.0", "2.0") < 0
assert apt_pkg.parse_depends("dpkg (>= 1)")[0][0][0] == "dpkg"
assert apt_pkg.TagSection("Package: dpkg\n")["Package"] == "dpkg"
assert apt.Cache()["dpkg"].is_installed
print("Python APT bindings can read the installed package database")
PYTHON
ln -sfn "$python_prefix/bin/python3.11" /usr/local/bin/python3.11
/usr/local/bin/python3.11 --version
