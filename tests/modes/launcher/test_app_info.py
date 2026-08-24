from __future__ import annotations

from ulauncher.modes.launcher.app_info import (
    app_action_ids,
    app_action_name,
    app_description,
    app_generic_name,
    app_id,
    app_keywords,
    app_name,
    collect_installed_app_matches,
    collect_usable_apps,
    describe_installed_app,
)


class _DesktopApp:
    def get_id(self) -> str:
        return "firefox.desktop"

    def get_name(self) -> str:
        return "Firefox"

    def get_generic_name(self) -> str:
        return "Web Browser"

    def get_keywords(self) -> list[str]:
        return ["browser"]

    def get_description(self) -> str:
        return "Browse the web"

    def list_actions(self) -> list[str]:
        return ["new-window", "private"]

    def get_action_name(self, action_id: str) -> str:
        return "Private" if action_id == "private" else action_id


class _InterfaceApp:
    def get_id(self) -> str:
        return "notes.desktop"

    def get_name(self) -> str:
        return "Notes"

    def get_description(self) -> str:
        return "Write notes"


class _BadEncodingApp:
    def get_id(self) -> str:
        message = "invalid desktop encoding"
        raise RuntimeError(message)


def test_app_info_skips_missing_desktop_methods() -> None:
    desktop = _DesktopApp()
    interface = _InterfaceApp()
    assert app_id(interface) == "notes.desktop"
    assert app_name(interface) == "Notes"
    assert app_generic_name(interface) == ""
    assert app_keywords(interface) == []
    assert app_description(interface) == "Write notes"
    assert app_action_ids(interface) == []
    assert app_action_name(interface, "private") == "private"
    assert app_keywords(desktop) == ["browser"]
    assert app_action_ids(desktop) == ["new-window", "private"]
    assert app_action_name(desktop, "private") == "Private"
    assert app_keywords(type("NullKeys", (), {"get_keywords": lambda _self: None})()) == []
    assert describe_installed_app(interface)["generic"] == ""
    assert describe_installed_app(type("Empty", (), {"get_id": lambda _self: ""})()) is None


def test_collect_installed_apps_isolates_bad_encoding() -> None:
    desktop = _DesktopApp()
    interface = _InterfaceApp()
    mixed = collect_installed_app_matches([_BadEncodingApp(), interface, desktop], "notes", lambda _app: True)
    assert len(mixed) == 1
    assert mixed[0]["title"] == "Notes"
    browser = collect_installed_app_matches([interface, desktop], "browser", lambda _app: True)
    assert len(browser) == 1
    assert browser[0]["title"] == "Firefox"
    assert collect_installed_app_matches([desktop], "fire", lambda app: app.get_name() == "hidden") == []
    assert collect_usable_apps([_BadEncodingApp(), interface], lambda _app: True) == [interface]
    assert collect_installed_app_matches([interface], "", lambda _app: True) == []
