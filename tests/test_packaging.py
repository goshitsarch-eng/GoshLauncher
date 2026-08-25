from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_file_is_gtk4_goshlauncher() -> None:
    desktop = (ROOT / "io.ulauncher.Ulauncher.desktop").read_text()
    assert "Name=GoshLauncher" in desktop
    assert "TryExec=ulauncher" in desktop
    assert "Exec=gapplication launch io.ulauncher.Ulauncher" in desktop
    assert "GTK 4" in desktop
    assert "Spotlight-goshos" in desktop


def test_debian_depends_on_gtk4_and_adwaita() -> None:
    control = (ROOT / "debian" / "control").read_text()
    assert "libgtk-4-1" in control
    assert "gir1.2-gtk-4.0" in control
    assert "libadwaita-1-0" in control
    assert "gir1.2-adw-1" in control
    assert "GTK 4 + libadwaita" in control
    assert "Ctrl+Space" in control


def test_setup_excludes_tests_from_install() -> None:
    setup = (ROOT / "setup.py").read_text()
    assert 'exclude=["tests", "tests.*", "conftest.py"]' in setup
    assert '"share/applications", ["io.ulauncher.Ulauncher.desktop"]' in setup
    assert '"bin/ulauncher"' in setup
    assert (ROOT / "bin" / "ulauncher").is_file()
