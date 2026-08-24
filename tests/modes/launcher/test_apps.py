from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.apps import (
    app_action_rows,
    app_base_name,
    app_match_tier,
    desktop_action_title,
    is_new_window_action,
    new_window_title,
    unique_by_base_name,
)


def test_app_base_name_strips_channel_suffix() -> None:
    assert app_base_name("Firefox ESR") == "firefox"
    assert app_base_name("Firefox") == "firefox"
    assert app_base_name("GNOME Builder") == "gnome builder"


def test_unique_by_base_name_keeps_first_sorted() -> None:
    esr = SimpleNamespace(name="Firefox ESR", app_id="firefox-esr.desktop")
    stable = SimpleNamespace(name="Firefox", app_id="firefox.desktop")
    unique = unique_by_base_name([stable, esr], 6)
    assert [app.name for app in unique] == ["Firefox"]


def test_app_match_tier_prefers_name_prefix() -> None:
    firefox = SimpleNamespace(
        name="Firefox",
        description="Web Browser",
        app_id="org.mozilla.firefox.desktop",
        keywords=["browser"],
    )
    assert app_match_tier(firefox, "fire") == 0
    assert app_match_tier(firefox, "browser") == 3
    assert app_match_tier(firefox, "mozilla") == 4
    assert app_match_tier(firefox, "zzz") == -1


def test_new_window_and_desktop_action_titles() -> None:
    assert is_new_window_action("new-window") is True
    assert is_new_window_action("new_window") is True
    assert is_new_window_action("open") is False
    assert new_window_title("Firefox") == "New window — Firefox"
    assert desktop_action_title("Private Window", "Firefox") == "Private Window — Firefox"


def test_app_action_rows_from_first_app() -> None:
    app = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        actions={
            "launch": {"name": "Launch"},
            "action:new-window": {"name": "New Window"},
            "action:private": {"name": "Private"},
        },
    )
    rows = app_action_rows(app, 6)
    assert [row["action_name"] for row in rows] == ["new-window", "private"]
    assert rows[0]["title"] == "New window — Firefox"
    assert rows[1]["title"] == "Private — Firefox"
    assert rows[0]["description"] == "Application action"
