import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).parents[1]
SPEC = REPO_ROOT / "packaging/fedora/goshlauncher.spec"
SOURCE_SCRIPT = REPO_ROOT / "packaging/fedora/make-source-archive.sh"
VERIFY_SCRIPT = REPO_ROOT / "packaging/fedora/verify-rpm.py"


def test_fedora_spec_has_native_identity_and_exact_dependencies() -> None:
    spec = SPEC.read_text()

    assert "Name:           goshlauncher" in spec
    assert "Version:        6.0.2" in spec
    assert "BuildArch:      noarch" in spec
    assert "License:        GPL-3.0-or-later AND LGPL-3.0-only" in spec
    assert "Vendor:         Gosh" in spec
    assert "URL:            https://github.com/goshitsarch-eng/GoshLauncher" in spec

    for dependency in (
        "python3-pyside6",
        "python3-xlib",
        "kf6-kirigami",
        "kf6-qqc2-desktop-style",
        "qt6-qtdeclarative",
        "xdg-utils",
        "python3-pip",
    ):
        assert f"Requires:       {dependency}" in spec

    for build_dependency in (
        "python3-devel",
        "pyproject-rpm-macros",
        "python3dist(setuptools)",
        "python3dist(setuptools-scm)",
        "desktop-file-utils",
        "appstream",
        "systemd-rpm-macros",
    ):
        assert f"BuildRequires:  {build_dependency}" in spec

    assert "%pyproject_wheel" in spec
    assert "%pyproject_install" in spec
    assert "%pyproject_save_files ulauncher" in spec


def test_fedora_payload_contract_and_policy() -> None:
    spec = SPEC.read_text()

    for installed_path in (
        "%{_bindir}/ulauncher",
        "%{_bindir}/ulauncher-toggle",
        "%{_datadir}/applications/com.goshapps.GoshLauncher.desktop",
        "%{_datadir}/dbus-1/services/com.goshapps.GoshLauncher.service",
        "%{_datadir}/metainfo/com.goshapps.GoshLauncher.metainfo.xml",
        "%{_userunitdir}/ulauncher.service",
        "%{_datadir}/ulauncher/",
        "%{_datadir}/icons/hicolor/scalable/apps/com.goshapps.GoshLauncher.svg",
        "%{_mandir}/man1/ulauncher.1*",
    ):
        assert installed_path in spec

    lower = spec.lower()
    for forbidden in (
        "flatpak-spawn",
        "org.freedesktop.flatpak",
        "goshlauncher-safe-host",
        "host_bridge",
        "host-bridge",
        "setcap",
    ):
        assert forbidden not in lower

    scriptlet_prefixes = ("%pre ", "%preun", "%post ", "%postun", "%trigger")
    assert not any(line.strip().lower().startswith(scriptlet_prefixes) for line in spec.splitlines())


def test_fedora_source_archive_and_rpm_verifier_are_reproducible_tools() -> None:
    source_script = SOURCE_SCRIPT.read_text()
    verifier = VERIFY_SCRIPT.read_text()

    assert 'git -C "$repo_root" archive' in source_script
    assert "gzip -n" in source_script
    assert "GoshLauncher-${version}.tar.gz" in source_script
    assert "rpm" in verifier
    assert "com.goshapps.GoshLauncher" in verifier
    assert "flatpak-spawn" in verifier
    assert "FILECAPS" in verifier
    assert "FILEMODES" in verifier
    assert "rpm2cpio" in verifier
    assert "cpio" in verifier


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("goshlauncher_rpm_verifier", VERIFY_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rpm_verifier_rejects_sibling_paths_and_scans_payload_bytes(tmp_path: Path) -> None:
    verifier = _load_verifier()

    assert verifier.path_is_allowed("/usr/bin/ulauncher")
    assert verifier.path_is_allowed("/usr/lib/python3.14/site-packages/ulauncher/core.py")
    assert verifier.path_is_allowed("/usr/lib/python3.14/site-packages/ulauncher-6.0.2.dist-info/METADATA")
    assert verifier.path_is_allowed("/usr/share/ulauncher/icons/gear.svg")
    assert not verifier.path_is_allowed("/usr/bin/ulauncher-rogue")
    assert not verifier.path_is_allowed("/usr/lib/python3.evil/arbitrary")
    assert not verifier.path_is_allowed("/usr/share/man/man1/ulauncher.1-backdoor")
    assert not verifier.path_is_allowed("/usr/share/ulauncher-backdoor/payload")

    clean = tmp_path / "clean.py"
    clean.write_text("print('native launcher')\n")
    assert verifier.find_forbidden_payload(tmp_path) == {}
    hostile = tmp_path / "hostile.py"
    hostile.write_text("subprocess.run(['flatpak-spawn', '--host'])\n")
    assert verifier.find_forbidden_payload(tmp_path) == {
        "flatpak-spawn": ["hostile.py"],
    }
