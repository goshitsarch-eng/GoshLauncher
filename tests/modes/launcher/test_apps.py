from __future__ import annotations

from types import SimpleNamespace

import pytest

from ulauncher.modes.launcher.apps import (
    app_action_rows,
    app_base_name,
    app_match_tier,
    app_row_description,
    app_window_count,
    desktop_action_title,
    is_new_window_action,
    match_apps,
    new_window_title,
    unique_by_base_name,
)
from ulauncher.modes.launcher.windows import WindowInfo


def test_app_base_name_strips_channel_suffix() -> None:
    assert app_base_name("Firefox ESR") == "firefox"
    assert app_base_name("Firefox") == "firefox"
    assert app_base_name("GNOME Builder") == "gnome builder"


def test_unique_by_base_name_keeps_first_sorted() -> None:
    esr = SimpleNamespace(name="Firefox ESR", app_id="firefox-esr.desktop")
    stable = SimpleNamespace(name="Firefox", app_id="firefox.desktop")
    unique = unique_by_base_name([stable, esr], 6)
    assert [app.name for app in unique] == ["Firefox"]


def test_app_match_tier_splits_generic_name_and_comment() -> None:
    firefox = SimpleNamespace(
        name="Firefox",
        generic_name="Web Browser",
        description="Browse the Web",
        app_id="org.mozilla.firefox.desktop",
        keywords=["internet"],
    )
    assert app_match_tier(firefox, "fire") == 0
    assert app_match_tier(firefox, "browser") == 3
    assert app_match_tier(firefox, "mozilla") == 4
    # "browse" is a prefix of GenericName "Browser", so it is a generic-name hit.
    assert app_match_tier(firefox, "browse") == 3
    assert app_match_tier(firefox, "ows") == -1
    assert app_match_tier(firefox, "zzz") == -1
    comment_only = SimpleNamespace(
        name="Firefox",
        generic_name="Web Browser",
        description="Surf the net",
        app_id="org.mozilla.firefox.desktop",
        keywords=["internet"],
    )
    assert app_match_tier(comment_only, "surf") == 6


def test_new_window_and_desktop_action_titles() -> None:
    assert is_new_window_action("new-window") is True
    assert is_new_window_action("new_window") is True
    assert is_new_window_action("open") is False
    assert new_window_title("Firefox") == "New window — Firefox"
    assert desktop_action_title("Private Window", "Firefox") == "Private Window — Firefox"


def test_app_action_rows_hide_new_window_when_not_running() -> None:
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
    idle = app_action_rows(app, 6, window_count=0)
    assert [row["action_name"] for row in idle] == ["private"]
    running = app_action_rows(app, 6, window_count=1)
    assert [row["action_name"] for row in running] == ["new-window", "private"]
    assert running[0]["title"] == "New window — Firefox"
    assert running[1]["title"] == "Private — Firefox"
    assert running[0]["description"] == "Application action"


def test_app_row_description_and_window_count() -> None:
    app = SimpleNamespace(app_id="firefox.desktop", _executable="firefox")
    windows = [
        WindowInfo(wid="1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=1),
        WindowInfo(wid="2", title="Terminal", wm_class="gnome-terminal.Gnome-terminal", desktop=0, pid=2),
    ]
    assert app_window_count(app, windows) == 1
    assert app_row_description(1) == "Switch to application"
    assert app_row_description(0) == "Application"


def test_match_apps_keeps_more_used_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    esr = SimpleNamespace(
        name="Firefox ESR",
        app_id="firefox-esr.desktop",
        generic_name="",
        description="",
        keywords=[],
    )
    stable = SimpleNamespace(
        name="Firefox",
        app_id="firefox.desktop",
        generic_name="",
        description="",
        keywords=[],
    )

    class _Rankings:
        def get_app_ids(self) -> list[str]:
            return ["firefox.desktop", "firefox-esr.desktop"]

    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [esr, stable])
    monkeypatch.setattr(apps_mod.AppRankings, "load", classmethod(lambda _cls: _Rankings()))
    matched = match_apps("fire", 6)
    assert [app.name for app in matched] == ["Firefox"]


def test_focus_open_windows_activates_matching_class(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.apps import focus_open_windows

    activated: list[dict] = []
    monkeypatch.setattr("ulauncher.modes.launcher.windows.activate_window", activated.append)
    app = SimpleNamespace(app_id="firefox.desktop", _executable="firefox")
    windows = [
        WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="Navigator.firefox", desktop=0, pid=11),
    ]
    assert focus_open_windows(app, windows) is True
    assert activated[0]["wid"] == "0x1"
    assert focus_open_windows(app, []) is False
