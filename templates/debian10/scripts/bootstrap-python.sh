#!/bin/sh
set -eu

# Keep Debian's /usr/bin/python3 for system packages. Ansible uses this
# relocatable, checksum-pinned Python instead of Buster's Python 3.7.
python_version=3.11.16
python_build=20260924
python_sha256=68c6739376b65258dee5058ccf6777232fe38d31a578965ae8bda327ec7da3a8
python_prefix=/opt/ludus/python3.11

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
archive="cpython-${python_version}+${python_build}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
curl --fail --location --silent --show-error \
    "https://github.com/astral-sh/python-build-standalone/releases/download/${python_build}/${archive}" \
    --output "$workdir/python.tar.gz"
printf '%s  %s\n' "$python_sha256" "$workdir/python.tar.gz" | sha256sum --check -

mkdir -p "$python_prefix"
tar -xzf "$workdir/python.tar.gz" --strip-components=1 -C "$python_prefix"
ln -sfn "$python_prefix/bin/python3.11" /usr/local/bin/python3.11
/usr/local/bin/python3.11 --version
