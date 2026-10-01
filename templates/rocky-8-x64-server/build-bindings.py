#!/usr/bin/env python3
"""Build Rocky's patched Python bindings against its installed native libraries.

All inputs are checksum-verified SRPMs prepared by bootstrap-python.sh. Never
install a native library or expose Python 3.6 site-packages to the private Python.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig


work = Path(sys.argv[1])
site = Path(sysconfig.get_path("platlib"))
python = sys.executable
os.environ.update(CC="gcc", CXX="g++", LDSHARED="gcc -shared")


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True)


def source(name, version):
    return work / name / "BUILD" / f"{name}-{version}"


def configure(path, replacements, destination=None):
    text = path.read_text()
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"Upstream build interface changed in {path}: {old!r}")
        text = text.replace(old, new)
    (destination or path).write_text(text)


def install_setup(directory):
    run(python, "setup.py", "build", cwd=directory)
    run(python, "setup.py", "install", "--skip-build", f"--prefix={sys.prefix}", cwd=directory)


# RPM's upstream setup.py supports out-of-tree linking through pkg-config.
# Exclude Makefile.am, which is its sentinel for linking in-tree RPM libraries.
rpm_source = source("rpm", "4.14.3") / "python"
rpm_build = work / "rpm-python"
shutil.copytree(rpm_source, rpm_build, ignore=shutil.ignore_patterns("Makefile.am"))
configure(
    rpm_build / "setup.py.in",
    {"@PACKAGE_NAME@": "rpm", "@VERSION@": "4.14.3", "@PACKAGE_BUGREPORT@": "rpm-maint@lists.rpm.org"},
    rpm_build / "setup.py",
)
install_setup(rpm_build)

# libcomps' upstream CMakeLists.txt lists exactly these extension sources.
# Compile that extension alone against libcomps-devel, not an in-tree libcomps.
comps = source("libcomps", "0.1.18") / "libcomps" / "src" / "python" / "src"
(comps / "setup.py").write_text('''from distutils.core import Extension, setup
setup(name="libcomps", version="0.1.18", packages=["libcomps"], ext_modules=[
    Extension("libcomps._libpycomps", sources=[
        "pycomps.c", "pycomps_sequence.c", "pycomps_envs.c", "pycomps_categories.c",
        "pycomps_groups.c", "pycomps_gids.c", "pycomps_utils.c", "pycomps_dict.c",
        "pycomps_mdict.c", "pycomps_hash.c", "pycomps_exc.c", "pycomps_lbw.c"],
        include_dirs=["../..", "/usr/include/libxml2"], libraries=["comps", "expat", "xml2"],
        extra_compile_args=["-std=c99", "-fno-strict-aliasing"])
])
''')
install_setup(comps)

# GPGME's Python build supports installed gpgme-config/gpg-error-config without
# configuring or building the native library. Generate its two version files.
gpg = source("gpgme", "1.13.1") / "lang" / "python"
for filename in ("setup.py", "version.py"):
    configure(gpg / f"{filename}.in", {"@VERSION@": "1.13.1"}, gpg / filename)
# SWIG does not follow the distro's C-preprocessor-only multilib wrapper.
# Feed its parser the matching x86_64 declarations, not an empty wrapper.
configure(gpg / "setup.py", {"'include', 'gpgme.h'": "'include', 'gpgme-64.h'"})
# Match Makefile.am's package preparation without configuring the native library.
(gpg / "gpg").symlink_to("src", target_is_directory=True)
install_setup(gpg)

# Retain Rocky's SELinux distutils patch (upstream 67d490a38a319126f371eaf66a5fc922d7005b1f,
# Petr Lautrbach): it installs the SWIG module inside the selinux package.
selinux = source("libselinux", "2.9") / "src"
run("make", "selinuxswig_python_exception.i", cwd=selinux)
install_setup(selinux)
shutil.copy2(selinux / "selinux.py", site / "selinux" / "__init__.py")

# Keep upstream's SWIG and hawkey target definitions. The sole target override
# uses the installed, ABI-matching libdnf rather than building a second copy.
libdnf = source("libdnf", "0.63.0")
configure(libdnf / "CMakeLists.txt", {
    "add_subdirectory(libdnf)": '''find_library(SYSTEM_LIBDNF NAMES dnf REQUIRED)
add_library(libdnf SHARED IMPORTED)
set_target_properties(libdnf PROPERTIES IMPORTED_LOCATION "${SYSTEM_LIBDNF}")''',
    # That subdirectory requires Sphinx even when WITH_HTML and WITH_MAN are off.
    "add_subdirectory(docs/hawkey)": "",
})
# Rocky's devel package omits this generated header; reproduce its x86_64 paths.
configure(libdnf / "libdnf" / "config-64.h.in",
          {"@MULTILIB_ARCH@": "64", "@CMAKE_INSTALL_FULL_LIBDIR@": "/usr/lib64"},
          libdnf / "libdnf" / "config-64.h")
shutil.copy2("/usr/include/libdnf/dnf-version.h", libdnf / "libdnf" / "dnf-version.h")
build = work / "libdnf-build"
run(
    "cmake", "-S", str(libdnf), "-B", str(build),
    f"-DPYTHON_EXECUTABLE={python}", f"-DPYTHON_DESIRED={python}",
    f"-DPYTHON_INCLUDE_DIR={sysconfig.get_path('include')}",
    f"-DPYTHON_LIBRARY={sys.prefix}/lib/libpython3.11.so",
    "-DWITH_GTKDOC=OFF", "-DWITH_HTML=OFF", "-DWITH_MAN=OFF", "-DWITH_ZCHUNK=OFF",
    "-DENABLE_RHSM_SUPPORT=OFF", "-DCMAKE_BUILD_TYPE=Release", cwd=work,
)
modules = ("error", "common_types", "conf", "module", "repo", "smartcols", "transaction", "utils")
run("cmake", "--build", str(build), "--parallel", str(os.cpu_count()), "--target",
    *(f"_{name}" for name in modules), "_hawkeymodule", cwd=work)
(site / "libdnf").mkdir(exist_ok=True)
shutil.copy2(libdnf / "bindings" / "python" / "__init__.py", site / "libdnf")
for name in modules:
    for filename in (f"{name}.py", f"_{name}.so"):
        shutil.copy2(build / "bindings" / "python" / filename, site / "libdnf")
shutil.copytree(build / "python" / "hawkey" / "hawkey", site / "hawkey", dirs_exist_ok=True)

# DNF is pure Python. Preserve Rocky's patches and /etc,/var defaults while
# resolving its default Python plugin directory under this private runtime.
dnf = source("dnf", "4.7.0") / "dnf"
configure(dnf / "const.py.in", {"@DNF_VERSION@": "4.7.0"}, dnf / "const.py")
shutil.copytree(dnf, site / "dnf", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("CMakeLists.txt", "*.in", "__pycache__"))
