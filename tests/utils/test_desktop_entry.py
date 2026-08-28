from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.utils.desktop_app import expand_exec
from ulauncher.utils.desktop_entry import DesktopEntry


@pytest.fixture
def entry(tmp_path: Path) -> DesktopEntry:
    desktop = tmp_path / "org.example.App.desktop"
    desktop.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Example",
                "Name[sv]=Exempel",
                "GenericName=Editor",
                "Comment=Edits\\sthings",
                "Icon=example",
                "Exec=env example %U --flag",
                "TryExec=/usr/bin/example-bin",
                "Keywords=alpha;beta;",
                "Terminal=false",
                "Actions=new-window;",
                "StartupWMClass=Example",
                "",
                "[Desktop Action new-window]",
                "Name=New Window",
                "Exec=example --new-window",
            ]
        )
    )
    loaded = DesktopEntry.from_file(str(desktop))
    assert loaded is not None
    return loaded


def test_basic_fields(entry: DesktopEntry) -> None:
    assert entry.name == "Example"
    assert entry.generic_name == "Editor"
    assert entry.comment == "Edits things"  # \s unescapes to a space
    assert entry.icon == "example"
    assert entry.keywords == ["alpha", "beta"]
    assert entry.executable == "example-bin"  # TryExec wins over the env wrapper in Exec
    assert entry.startup_wm_class == "Example"
    assert not entry.terminal
    assert not entry.hidden


def test_actions(entry: DesktopEntry) -> None:
    actions = entry.get_actions()
    assert list(actions) == ["new-window"]
    assert actions["new-window"]["name"] == "New Window"
    assert entry.get_action_exec("new-window") == "example --new-window"


def test_show_in_filtering(entry: DesktopEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert entry.show_in_current_desktop()
    entry._groups["Desktop Entry"]["OnlyShowIn"] = "GNOME;"
    assert not entry.show_in_current_desktop()
    entry._groups["Desktop Entry"]["OnlyShowIn"] = "KDE;"
    assert entry.show_in_current_desktop()
    entry._groups["Desktop Entry"]["NotShowIn"] = "KDE;"
    assert not entry.show_in_current_desktop()


def test_non_application_entries_are_rejected(tmp_path: Path) -> None:
    link = tmp_path / "link.desktop"
    link.write_text("[Desktop Entry]\nType=Link\nName=A link\nURL=https://example.com\n")
    assert DesktopEntry.from_file(str(link)) is None


class TestExpandExec:
    def test_uri_field_codes(self) -> None:
        argv = expand_exec("app %U --flag", uris=["smb://nas.local/media"])
        assert argv == ["app", "smb://nas.local/media", "--flag"]

    def test_file_field_codes_strip_the_scheme(self) -> None:
        argv = expand_exec("app %f", uris=["file:///home/u/a b.txt"])
        assert argv == ["app", "/home/u/a b.txt"]

    def test_unused_field_codes_are_dropped(self) -> None:
        assert expand_exec("app %U %i %c") == ["app"]

    def test_unparseable_line(self) -> None:
        assert expand_exec('app "unterminated') is None
