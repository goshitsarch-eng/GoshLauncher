from __future__ import annotations

from pathlib import Path

from ulauncher import app_display_name, show_launcher_label
from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK

ROOT = Path(__file__).resolve().parents[1]


def test_product_name_and_show_label() -> None:
    assert app_display_name == "GoshLauncher"
    assert show_launcher_label == "Show GoshLauncher"
    assert DEFAULT_FALLBACK == "<Control>space"
    app_src = (ROOT / "ulauncher" / "ui" / "app.py").read_text()
    assert "DEFAULT_FALLBACK" in app_src
    assert 'or "<Control>space"' not in app_src
    tray_src = (ROOT / "ulauncher" / "ui" / "helpers" / "tray_icon.py").read_text()
    assert "show_launcher_label" in tray_src
    assert "Show Ulauncher" not in tray_src


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
    assert "https://github.com/goshitsarch-eng/GoshLauncher" in control


def test_pyproject_points_at_goshlauncher() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    assert 'description = "GTK 4 + libadwaita launcher matching Spotlight-goshos"' in text
    assert "https://github.com/goshitsarch-eng/GoshLauncher" in text
    assert "http://ulauncher.io/" not in text
    gtk4 = (ROOT / "ulauncher" / "ui" / "gtk4.py").read_text()
    assert "ContentProvider.new_for_bytes" in gtk4
    assert "clipboard.set(text)" not in gtk4


def test_setup_excludes_tests_from_install() -> None:
    setup = (ROOT / "setup.py").read_text()
    assert 'exclude=["tests", "tests.*", "conftest.py"]' in setup
    assert '"share/applications", ["io.ulauncher.Ulauncher.desktop"]' in setup
    assert '"bin/ulauncher"' in setup
    assert (ROOT / "bin" / "ulauncher").is_file()


def test_ci_installs_gtk4_on_ubuntu_22_04() -> None:
    tests = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    script = (ROOT / "scripts" / "ci-install-gtk4.sh").read_text()
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text()
        assert "ulauncher/build-image" not in text, path.name
    assert "ubuntu-22.04" in tests
    assert "scripts/ci-install-gtk4.sh" in tests
    draft = (ROOT / ".github" / "workflows" / "draft-release.yml").read_text()
    assert "scripts/ci-install-gtk4.sh" in draft
    assert "preferences-src" not in draft
    publish = (ROOT / ".github" / "workflows" / "publish-release.yml").read_text()
    assert "scripts/ci-install-gtk4.sh" in publish
    assert "ubuntu-22.04" in publish
    assert "help2man" in publish
    assert "help2man" in draft
    makefile = (ROOT / "makefile").read_text()
    assert "command -v help2man" in makefile
    assert "gir1.2-gtk-4.0" in script
    assert "gir1.2-adw-1" in script
    assert "libadwaita-1-0" in script
    makefile = (ROOT / "makefile").read_text()
    assert 'export PATH="/usr/sbin:/usr/bin:/sbin:/bin"' in makefile


def test_pyrefly_typechecks_shipped_package() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'project-includes = ["ulauncher"]' in pyproject
    assert 'project-includes = ["ulauncher", "tests"]' not in pyproject
    assert "implicit-any-type-argument = false" in pyproject
    assert "invalid-inheritance = false" in pyproject
    assert "unnecessary-type-conversion = false" in pyproject
    assert 'min-severity = "error"' in pyproject


def test_venv_bootstraps_pip_before_pygobject_stubs() -> None:
    makefile = (ROOT / "makefile").read_text()
    venv = makefile[makefile.index("venv:") : makefile.index("-r requirements.txt")]
    assert "pip install --ignore-installed --upgrade" in venv
    assert "setuptools>=65" in venv
    pins = [
        line.split("#", 1)[0].strip()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line.split("#", 1)[0].strip()
    ]
    assert "pygobject-stubs==2.12.0" in pins


def test_prerelease_banner_uses_goshlauncher() -> None:
    from ulauncher.cli.commands.start import _boxed_warning

    banner = _boxed_warning(f"YOU ARE RUNNING A PRE-RELEASE of {app_display_name.upper()}.")
    assert "GOSHLAUNCHER" in banner
    assert "PRE-RELEASE of ULAUNCHER" not in banner
    start = (ROOT / "ulauncher" / "cli" / "commands" / "start.py").read_text()
    assert "PRE-RELEASE of ULAUNCHER" not in start
    assert "render Ulauncher correctly" not in start
    assert "app_display_name" in start
    plasma = _boxed_warning(f"Plasma Desktop needs Layer Shell to render {app_display_name} correctly on Wayland.")
    assert "GoshLauncher" in plasma
    assert "Ulauncher" not in plasma


def test_fork_attribution_is_stated() -> None:
    # GPL-3.0 5(a): a modified Ulauncher has to carry prominent notices saying so.
    authors = (ROOT / "AUTHORS").read_text()
    assert "fork of Ulauncher" in authors
    assert "Aleksandr Gornostal" in authors
    assert "spotlight-goshos" in authors
    assert "GoshLauncher" in authors

    readme = (ROOT / "README.md").read_text()
    assert "## Credits" in readme
    assert "https://github.com/Ulauncher/Ulauncher" in readme
    assert "https://github.com/goshitsarch-eng/spotlight-goshos" in readme
    assert "GPL-3.0 section 5(a)" in readme

    copyright_file = (ROOT / "debian" / "copyright").read_text()
    assert "goshitsarch-eng/GoshLauncher" in copyright_file
    assert "Aleksandr Gornostal" in copyright_file


def test_release_does_not_publish_into_upstreams_channels() -> None:
    # A fork must never upload to Ulauncher's PPA or take over its AUR package.
    workflow = (ROOT / ".github" / "workflows" / "publish-release.yml").read_text()
    assert "agornostal/ulauncher" not in workflow
    assert "package_name: ulauncher" not in workflow
    assert 'commit_username: "Ulauncher"' not in workflow
    # both publish steps are opt-in, so an unconfigured fork uploads nowhere
    assert "vars.LAUNCHPAD_PPA" in workflow
    assert "vars.AUR_PACKAGE_NAME" in workflow

    cliff = (ROOT / "cliff.toml").read_text()
    assert "Ulauncher/Ulauncher" not in cliff


def test_vendored_pyewmh_keeps_its_own_licence() -> None:
    ewmh = (ROOT / "ulauncher" / "utils" / "ewmh.py").read_text()
    assert "pyewmh" in ewmh
    assert "Lesser General Public License" in ewmh
    copyright_file = (ROOT / "debian" / "copyright").read_text()
    assert "Files: ulauncher/utils/ewmh.py" in copyright_file
    assert "License: LGPL-3" in copyright_file
    assert "pyewmh" in (ROOT / "AUTHORS").read_text()


def test_manpage_version_matches_the_package() -> None:
    from ulauncher import version

    # `make manpage` used to stamp whatever ${VERSION} held when make parsed the file, so a
    # release that had just bumped the version wrote the previous one into the manpage.
    assert f"ulauncher {version}" in (ROOT / "ulauncher.1").read_text()
    makefile = (ROOT / "makefile").read_text()
    assert '--version-string="ulauncher $$(sed -n' in makefile


def test_contributor_docs_point_at_this_fork() -> None:
    # Verbatim upstream docs sent GoshLauncher contributors to Ulauncher's tracker.
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    assert "GoshLauncher is a fork" in contributing
    assert "goshitsarch-eng/GoshLauncher/issues" in contributing
    assert "contributing to Ulauncher!" not in contributing

    conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text()
    assert conduct.startswith("# GoshLauncher Code of Conduct")
    assert "Inherited from Ulauncher" in conduct


def test_scrollbar_slider_box_is_restated_after_the_reset() -> None:
    # `.app *` strips the transparent border libadwaita uses to cancel the slider's negative
    # margin, so the gizmo measured -4: two GTK warnings per overflowing popup and a 0px trough.
    css = (ROOT / "data" / "themes" / "gosh-looks.css").read_text()
    rule = css[css.index(".app scrollbar slider {") :].split("}", 1)[0]
    assert "margin: 0;" in rule
    assert "min-width: 8px;" in rule
    assert "min-height: 40px;" in rule


def test_global_shortcut_rebind_closes_the_previous_portal_session() -> None:
    source = (ROOT / "ulauncher" / "modes" / "launcher" / "global_shortcuts.py").read_text()
    # Without this the portal keeps the old accelerator grabbed, so both combinations open the
    # launcher and each rebind leaks another session.
    start = source[source.index("    def start(") :]
    assert "self._close_session()" in start.split("def _on_create_session_response", 1)[0]
    assert '"org.freedesktop.portal.Session"' in source
