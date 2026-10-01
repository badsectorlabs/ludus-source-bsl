#!/bin/bash
# Build only private Python extensions; never replace Rocky's platform-python,
# /usr/bin/python3, DNF, RPM, or their native shared libraries.
set -euo pipefail
umask 022

prefix=/opt/ludus/python3.11
work=$(mktemp -d /var/tmp/ludus-rocky-python.XXXXXXXX)
trap 'rm -rf "$work"' EXIT

# PowerTools supplies development headers, not replacement runtime packages.
# Packages are authenticated by Rocky's enabled repository GPG checks.
dnf -y --enablerepo=powertools install \
    ca-certificates curl tar gzip bzip2 xz make gcc gcc-c++ cmake git \
    rpm-build redhat-rpm-config python3-rpm-macros patch gettext \
    rpm-devel libdnf-devel libcomps-devel libselinux-devel libsepol-static \
    gpgme-devel libgpg-error-devel libassuan-devel \
    libsolv-devel librepo-devel libmodulemd-devel glib2-devel \
    json-c-devel sqlite-devel libsmartcols-devel openssl-devel \
    check-devel cppunit-devel expat-devel libxml2-devel zlib-devel

fetch() {
    local url=$1 checksum=$2 destination=$3
    curl --fail --location --show-error --silent --proto '=https' \
        "$url" --output "$destination"
    printf '%s  %s\n' "$checksum" "$destination" | sha256sum --check --strict
}

fetch 'https://github.com/astral-sh/python-build-standalone/releases/download/20260924/cpython-3.11.16+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz' \
    68c6739376b65258dee5058ccf6777232fe38d31a578965ae8bda327ec7da3a8 \
    "$work/python.tar.gz"
install -d "$prefix"
tar -xzf "$work/python.tar.gz" -C "$prefix" --strip-components=1
python="$prefix/bin/python3.11"

# SWIG 4.2 supports Python 3.11 and the two-argument AppendOutput typemaps in
# Rocky's SELinux/libdnf sources; SWIG 4.3 changes that generated-code interface.
# Source digest: https://lists.nongnu.org/archive/html/guix-patches/2024-03/msg00181.html
fetch 'https://downloads.sourceforge.net/project/swig/swig/swig-4.2.1/swig-4.2.1.tar.gz' \
    fa045354e2d048b2cddc69579e4256245d4676894858fcf0bab2290ecf59b7d8 \
    "$work/swig.tar.gz"
tar -xzf "$work/swig.tar.gz" -C "$work"
(
    cd "$work/swig-4.2.1"
    ./configure --prefix="$work/swig" --without-pcre --without-alllang
    make -j"$(nproc)"
    make install
)
export PATH="$work/swig/bin:$PATH"
# Use CPython's bundled distutils, avoiding unpinned pip/build dependencies.
export SETUPTOOLS_USE_DISTUTILS=stdlib

prepare() {
    local name=$1 source=$2 checksum=$3 runtime=$4
    local top="$work/$name"
    local installed
    installed=$(rpm -q --qf '%{SOURCERPM}' "$runtime")
    if [[ "$installed" != "$source.src.rpm" ]]; then
        printf 'Native binding pin mismatch: %s uses %s, expected %s.src.rpm. Update the source pin with the Rocky package.\n' \
            "$runtime" "$installed" "$source" >&2
        exit 1
    fi
    mkdir -p "$top"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
    fetch "https://download.rockylinux.org/pub/rocky/8/BaseOS/source/tree/Packages/${name:0:1}/$source.src.rpm" \
        "$checksum" "$top/source.rpm"
    rpm --define "_topdir $top" -i "$top/source.rpm"
    # -bp applies the complete vendor patch stack; it neither builds nor
    # installs an RPM. --nodeps omits unrelated full-library/doc build deps.
    rpmbuild --define "_topdir $top" -bp --nodeps "$top/SPECS/$name.spec"
}

prepare rpm rpm-4.14.3-32.el8_10 \
    fb04346e9e1980eeecc9dd1916cc8cac918ca519719cf45a406dec956f0170c1 rpm-libs
prepare libdnf libdnf-0.63.0-21.el8_10 \
    3a4adb51deb47c92afd4302d6e38c181f265ba363e1037aa67eb9161a42c5728 libdnf
prepare libcomps libcomps-0.1.18-1.el8 \
    bbd9d17b2a84736caa224684d9d13ace6361ac52f30544ca427421d5b86468d6 libcomps
prepare libselinux libselinux-2.9-11.el8_10 \
    2d991c9282b4d253fb04e8f85d8272c01cf41d4b721f91afb563b479d8724776 libselinux
prepare gpgme gpgme-1.13.1-12.el8 \
    73facbad8d02769c7c90b25ffa4454aef111d6053f602c10cb4564490f3d81de gpgme
prepare dnf dnf-4.7.0-21.el8_10 \
    eae2781f335076ace577d95221401318f02c75ccb70d9548ec2362d2431e3f88 python3-dnf

"$python" /var/tmp/ludus-build-bindings.py "$work"
# Fail the template build on missing extensions, broken RPM database access,
# missing releasever/repositories, or broken SELinux calls, not just imports.
"$python" - <<'PY'
import sys
import dnf
import gpg
import hawkey
import libcomps
import libdnf
import rpm
import selinux
assert sys.version_info[:2] == (3, 11)
assert rpm.TransactionSet().dbMatch('name', 'rpm').count() == 1
with dnf.Base() as base:
    base.conf.read()
    base.read_all_repos()
    assert base.conf.substitutions['releasever'].startswith('8')
    assert {'baseos', 'appstream'} <= {repo.id for repo in base.repos.iter_enabled()}
    base.fill_sack(load_system_repo=True, load_available_repos=False)
    assert list(base.sack.query().installed().filter(name='rpm'))
assert selinux.is_selinux_enabled() in (0, 1)
assert selinux.matchpathcon('/etc/passwd', 0)[0] == 0
print('Private Python 3.11: native bindings, RPM database, DNF configuration and SELinux OK')
PY
/usr/libexec/platform-python -c 'import sys, dnf, rpm, selinux; assert sys.version_info[:2] == (3, 6)'
/usr/bin/dnf --version

# Discovery prefers python3.11 to Rocky's unsupported python3.6. Packer also
# sets the interpreter explicitly, before its first fact-gathering task.
ln -sfn "$python" /usr/local/bin/python3.11
restorecon -RF "$prefix" /usr/local/bin/python3.11

rm -f /var/tmp/ludus-build-bindings.py
dnf clean all
