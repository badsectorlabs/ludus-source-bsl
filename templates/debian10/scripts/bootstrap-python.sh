#!/bin/sh
set -eu

# Keep Debian's /usr/bin/python3 for system packages. Ansible uses this
# relocatable, checksum-pinned Python instead of Buster's Python 3.7.
python_version=3.11.16
python_build=20260924
python_sha256=68c6739376b65258dee5058ccf6777232fe38d31a578965ae8bda327ec7da3a8
python_prefix=/opt/ludus/python3.11
python_apt_version=1.8.4.3
python_apt_sha256=69ea6bdb0b0f23f58be63af51c4f8da24000051e710f0a927d6a936677d097eb

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl g++ libapt-pkg-dev patch xz-utils

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
archive="cpython-${python_version}+${python_build}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
curl --fail --location --silent --show-error \
    "https://github.com/astral-sh/python-build-standalone/releases/download/${python_build}/${archive}" \
    --output "$workdir/python.tar.gz"
printf '%s  %s\n' "$python_sha256" "$workdir/python.tar.gz" | sha256sum --check -

mkdir -p "$python_prefix"
tar -xzf "$workdir/python.tar.gz" --strip-components=1 -C "$python_prefix"

# Buster's python3-apt is compiled for Python 3.7. Build the matching APT
# bindings for the private interpreter, without replacing system Python/APT.
curl --fail --location --silent --show-error \
    "https://archive.debian.org/debian/pool/main/p/python-apt/python-apt_${python_apt_version}.tar.xz" \
    --output "$workdir/python-apt.tar.xz"
printf '%s  %s\n' "$python_apt_sha256" "$workdir/python-apt.tar.xz" | sha256sum --check -
tar -xJf "$workdir/python-apt.tar.xz" -C "$workdir"
apt_source="$workdir/python-apt-${python_apt_version}"

# Backport the size types from upstream's Python 3.10+ compatibility fix.
# https://salsa.debian.org/apt-team/python-apt/-/commit/6b70382816e984d46a72f489c50b5ec6a326b0a0
# PY_SSIZE_T_CLEAN below must be paired with these Py_ssize_t arguments.
patch --batch --fuzz=0 -p1 -d "$apt_source" <<'PATCH'
--- a/python/apt_pkgmodule.cc
+++ b/python/apt_pkgmodule.cc
@@ -84,8 +84,8 @@
 {
    char *A;
    char *B;
-   int LenA;
-   int LenB;
+   Py_ssize_t LenA;
+   Py_ssize_t LenB;
 
    if (PyArg_ParseTuple(Args,"s#s#",&A,&LenA,&B,&LenB) == 0)
       return 0;
@@ -188,7 +188,7 @@
 
    const char *Start;
    const char *Stop;
-   int Len;
+   Py_ssize_t Len;
    const char *Arch = NULL;
    char *kwlist[] = {"s", "strip_multi_arch", "architecture", 0};
 
--- a/python/tag.cc
+++ b/python/tag.cc
@@ -448,7 +448,7 @@
 static PyObject *TagSecNew(PyTypeObject *type,PyObject *Args,PyObject *kwds) {
    char *Data;
-   int Len;
+   Py_ssize_t Len;
    char Bytes = 0;
    char *kwlist[] = {"text", "bytes", 0};
 
    // this allows reading "byte" types from python3 - but we don't
PATCH
(
    cd "$apt_source"
    CC=gcc CXX=g++ LDSHARED='g++ -shared' CFLAGS='-O2 -DPY_SSIZE_T_CLEAN' \
        SETUPTOOLS_USE_DISTUTILS=stdlib DEBVER="$python_apt_version" \
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
