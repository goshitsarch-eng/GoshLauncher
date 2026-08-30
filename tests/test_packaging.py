from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import ulauncher
from ulauncher import app_display_name, show_launcher_label
from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "com.goshapps.GoshLauncher"
DESKTOP_FILE = ROOT / f"{APP_ID}.desktop"
DBUS_SERVICE_FILE = ROOT / f"{APP_ID}.service"
METAINFO_FILE = ROOT / f"{APP_ID}.metainfo.xml"


def test_product_name_and_show_label() -> None:
    assert ulauncher.app_id == APP_ID
    assert ulauncher.dbus_path == "/com/goshapps/GoshLauncher"
    assert app_display_name == "GoshLauncher"
    assert show_launcher_label == "Show GoshLauncher"
    assert DEFAULT_FALLBACK == "<Control>space"
    app_src = (ROOT / "ulauncher" / "ui" / "app.py").read_text()
    assert "DEFAULT_FALLBACK" in app_src
    assert 'or "<Control>space"' not in app_src
    tray_src = (ROOT / "ulauncher" / "ui" / "tray_icon.py").read_text()
    assert "show_launcher_label" in tray_src
    assert "Show Ulauncher" not in tray_src


def test_desktop_file_is_qt6_goshlauncher() -> None:
    desktop = DESKTOP_FILE.read_text()
    assert "Name=GoshLauncher" in desktop
    assert f"Icon={APP_ID}" in desktop
    assert "TryExec=ulauncher" in desktop
    assert "Exec=ulauncher show" in desktop
    assert "Kirigami" in desktop
    assert "gapplication" not in desktop


def test_freedesktop_identity_is_canonical_and_synchronized() -> None:
    desktop = DESKTOP_FILE.read_text()
    dbus_service = DBUS_SERVICE_FILE.read_text()
    systemd_service = (ROOT / "ulauncher.service").read_text()
    setup = (ROOT / "setup.py").read_text()
    # This parses repository-controlled static metadata, never untrusted XML.
    metadata = ET.parse(METAINFO_FILE).getroot()  # noqa: S314
    launchable = metadata.find("launchable")
    release = metadata.find("releases/release")

    assert desktop.startswith("[Desktop Entry]\n")
    assert f"Name={APP_ID}" in dbus_service
    assert f"BusName={APP_ID}" in systemd_service
    assert metadata.findtext("id") == APP_ID
    assert metadata.findtext("name") == "GoshLauncher"
    assert metadata.findtext("developer/name") == "Gosh"
    assert launchable is not None
    assert launchable.attrib == {"type": "desktop-id"}
    assert metadata.findtext("launchable") == f"{APP_ID}.desktop"
    assert release is not None
    assert release.attrib["version"] == ulauncher.version
    assert f'"share/applications", ["{APP_ID}.desktop"]' in setup
    assert f'"share/dbus-1/services", ["{APP_ID}.service"]' in setup
    assert f'"share/metainfo", ["{APP_ID}.metainfo.xml"]' in setup
    assert not (ROOT / "io.ulauncher.Ulauncher.desktop").exists()
    assert not (ROOT / "io.ulauncher.Ulauncher.service").exists()


def test_ulauncher_data_and_extension_compatibility_paths_are_preserved() -> None:
    assert Path(ulauncher.paths.CONFIG).name == "ulauncher"
    assert Path(ulauncher.paths.DATA).name == "ulauncher"
    assert Path(ulauncher.paths.STATE).name == "ulauncher"
    assert Path(ulauncher.paths.USER_EXTENSIONS).name == "extensions"
    assert (ROOT / "bin" / "ulauncher").is_file()
    assert (ROOT / "bin" / "ulauncher-toggle").is_file()
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'name = "ulauncher"' in pyproject
    assert 'api_version = "3.0"' in (ROOT / "ulauncher" / "__init__.py").read_text()


def test_debian_depends_on_qt6_and_kirigami() -> None:
    control = (ROOT / "debian" / "control").read_text()
    assert "python3-pyside6.qtqml" in control
    assert "qml6-module-org-kde-kirigami" in control
    assert "Qt 6 + Kirigami" in control
    assert "Ctrl+Space" in control
    assert "https://github.com/goshitsarch-eng/GoshLauncher" in control
    assert "libgtk" not in control
    assert "libadwaita" not in control


def test_pyproject_points_at_goshlauncher() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    assert 'description = "Qt 6 + Kirigami launcher matching Spotlight-goshos"' in text
    assert "https://github.com/goshitsarch-eng/GoshLauncher" in text
    assert "http://ulauncher.io/" not in text
    assert "PySide6" in text
    assert "PyGObject" not in text
    assert 'authors = [{name = "Gosh"}]' in text


def test_container_build_has_no_gtk_or_pygobject_dependencies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    forbidden = (
        "gobject-introspection",
        "python3-gi",
        "gir1.2-",
        "libgtk",
        "libadwaita",
        "libgirepository",
        "libcairo",
        "PyGObject",
        "pycairo",
    )
    assert not any(item in dockerfile for item in forbidden)


def test_canonical_icon_and_product_wording_are_exclusive() -> None:
    assert not (ROOT / "data/icons/system/apps/ulauncher.svg").exists()
    notify = (ROOT / "ulauncher/ui/notify.py").read_text()
    preview = (ROOT / "ulauncher/cli/commands/preview.py").read_text()
    launcher = (ROOT / "bin/ulauncher").read_text()
    authors = (ROOT / "AUTHORS").read_text()
    assert "icon: str = app_id" in notify
    assert "GoshLauncher needs to be running" in preview
    assert "along with GoshLauncher's" in preview
    assert "reinstall of GoshLauncher" in launcher
    assert "GTK 4 + libadwaita popup" not in authors


def test_no_gobject_introspection_left() -> None:
    """The Qt rewrite must not regress back into GTK/GLib bindings."""
    for path in (ROOT / "ulauncher").rglob("*.py"):
        text = path.read_text()
        assert "gi.repository" not in text, path
        assert "from ulauncher.gi" not in text, path


def test_qml_ui_ships_with_the_package() -> None:
    qml_dir = ROOT / "ulauncher" / "ui" / "qml"
    assert (qml_dir / "LauncherWindow.qml").is_file()
    assert (qml_dir / "PreferencesWindow.qml").is_file()
    setup = (ROOT / "setup.py").read_text()
    assert '"ulauncher.ui": ["qml/*.qml"]' in setup
    # The launcher and preferences must be Kirigami-styled
    for name in ("LauncherWindow.qml", "PreferencesWindow.qml"):
        assert "org.kde.kirigami" in (qml_dir / name).read_text(), name


def test_setup_excludes_tests_from_install() -> None:
    setup = (ROOT / "setup.py").read_text()
    assert 'exclude=["tests", "tests.*", "conftest.py"]' in setup
    assert f'"share/applications", ["{APP_ID}.desktop"]' in setup
    assert '"bin/ulauncher"' in setup
    assert (ROOT / "bin" / "ulauncher").is_file()


def test_ci_installs_qt6() -> None:
    tests = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    script = (ROOT / "scripts" / "ci-install-qt6.sh").read_text()
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text()
        assert "ulauncher/build-image" not in text, path.name
        assert "ci-install-gtk4" not in text, path.name
    assert "scripts/ci-install-qt6.sh" in tests
    draft = (ROOT / ".github" / "workflows" / "draft-release.yml").read_text()
    assert "scripts/ci-install-qt6.sh" in draft
    publish = (ROOT / ".github" / "workflows" / "publish-release.yml").read_text()
    assert "scripts/ci-install-qt6.sh" in publish
    assert "help2man" in publish
    assert "help2man" in draft
    makefile = (ROOT / "makefile").read_text()
    assert "command -v help2man" in makefile
    assert "libegl1" in script
