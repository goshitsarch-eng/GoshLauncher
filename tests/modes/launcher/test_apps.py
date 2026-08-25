from __future__ import annotations

from types import SimpleNamespace

import pytest

from ulauncher.modes.launcher.apps import (
    app_action_rows,
    app_base_name,
    app_is_unique_gtk,
    app_match_tier,
    app_muxer_has_new_window,
    app_row_description,
    app_window_count,
    can_open_new_window,
    desktop_action_title,
    has_desktop_new_window_action,
    home_apps,
    is_new_window_action,
    match_apps,
    muxer_has_new_window_action,
    new_window_title,
    open_new_window,
    take_app_actions,
    unique_by_base_name,
)
from ulauncher.modes.launcher.windows import WindowInfo


def test_app_base_name_strips_channel_suffix() -> None:
    assert app_base_name("Firefox ESR") == "firefox"
    assert app_base_name("Firefox") == "firefox"
    assert app_base_name("GNOME Builder") == "gnome builder"
    assert app_base_name("GNOME-Builder") == "gnome-builder"


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
    assert app_match_tier(firefox, "org") == -1
    assert app_match_tier(firefox, "zil") == -1
    assert app_match_tier(firefox, "f") == 0
    assert app_match_tier(firefox, "") == -1
    assert app_match_tier(firefox, "zzz") == -1
    files = SimpleNamespace(
        name="Files",
        generic_name="",
        description="",
        app_id="org.gnome.Nautilus.desktop",
        keywords=[],
    )
    assert app_match_tier(files, "nautilus") == 4
    assert app_match_tier(files, "o") == -1
    chrome = SimpleNamespace(
        name="Google Chrome",
        generic_name="Web Browser",
        description="",
        app_id="google-chrome.desktop",
        keywords=["browser"],
    )
    assert app_match_tier(chrome, "chro") == 1
    assert app_match_tier(chrome, "chrome browser") >= 0
    assert app_match_tier(firefox, "firefox browser") >= 0
    notes = SimpleNamespace(
        name="Notes",
        generic_name="",
        description="",
        app_id="notes.desktop",
        keywords=[],
    )
    assert app_match_tier(notes, "chrome browser") == -1
    keyed = SimpleNamespace(
        name="Firefox",
        generic_name="",
        description="",
        app_id="firefox.desktop",
        keywords=["Internet", "Browser"],
    )
    assert app_match_tier(keyed, "browser") == 5
    assert app_match_tier(keyed, "row") == -1
    comment = SimpleNamespace(
        name="Notes",
        generic_name="",
        description="Write notes and lists",
        app_id="notes.desktop",
        keywords=[],
    )
    assert app_match_tier(comment, "write") == 6
    assert app_match_tier(comment, "ite") == -1
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
    assert is_new_window_action("new-private-window") is False
    assert is_new_window_action("open") is False
    assert new_window_title("Firefox") == "New window — Firefox"
    assert desktop_action_title("Private Window", "Firefox") == "Private Window — Firefox"
    assert take_app_actions(["a", "b", "c"], 2) == ["a", "b"]
    assert take_app_actions(["a"], 0) == []


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
    assert running[0]["synthetic_new_window"] is True
    assert running[0]["icon"] == "application-x-executable-symbolic"
    assert running[1]["title"] == "Private — Firefox"
    assert running[0]["description"] == "Application action"
    notes = SimpleNamespace(
        name="Notes",
        icon="notes",
        app_id="notes.desktop",
        actions={"launch": {"name": "Launch"}, "action:new": {"name": "New Document"}},
    )
    synthesized = app_action_rows(notes, 6, window_count=2)
    assert [row["action_name"] for row in synthesized] == ["new-window", "new"]
    assert synthesized[0]["title"] == "New window — Notes"
    assert synthesized[0]["synthetic_new_window"] is True
    assert app_action_rows(notes, 6, window_count=0)[0]["action_name"] == "new"


def test_single_window_apps_skip_synthetic_new_window() -> None:
    settings = SimpleNamespace(
        name="Settings",
        icon="settings",
        app_id="org.gnome.Settings.desktop",
        actions={"launch": {"name": "Launch"}, "action:about": {"name": "About"}},
        single_window=True,
    )
    assert can_open_new_window(0, settings) is False
    assert can_open_new_window(1, settings) is False
    assert can_open_new_window(1, SimpleNamespace()) is True
    assert has_desktop_new_window_action(settings) is False
    rows = app_action_rows(settings, 6, window_count=2)
    assert [row["action_name"] for row in rows] == ["about"]
    assert all(not row.get("synthetic_new_window") for row in rows)


def test_unique_gtk_apps_skip_synthetic_new_window_unless_desktop_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    monkeypatch.setattr(apps_mod, "probe_gtk_actions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(apps_mod, "list_gtk_action_names", lambda *_args, **_kwargs: [])
    settings = SimpleNamespace(
        name="Settings",
        icon="settings",
        app_id="org.gnome.Settings.desktop",
        actions={"launch": {"name": "Launch"}, "action:about": {"name": "About"}},
        single_window=False,
    )
    unique = WindowInfo(
        wid="0x1",
        title="Settings",
        wm_class="org.gnome.Settings",
        desktop=0,
        gtk_app_id="org.gnome.Settings",
        gtk_unique_bus_name=":1.42",
        gtk_application_object_path="/org/gnome/Settings",
    )
    assert app_is_unique_gtk(settings, [unique]) is True
    assert can_open_new_window(1, settings, unique_gtk=True) is False
    assert can_open_new_window(1, settings, windows=[unique]) is False
    rows = app_action_rows(settings, 6, window_count=1, windows=[unique])
    assert [row["action_name"] for row in rows] == ["about"]
    firefox = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        actions={
            "launch": {"name": "Launch"},
            "action:new-window": {"name": "New Window"},
            "action:private": {"name": "Private"},
        },
        single_window=False,
    )
    assert has_desktop_new_window_action(firefox) is True
    assert can_open_new_window(1, firefox, unique_gtk=True) is True
    firefox_win = WindowInfo(
        wid="0x2",
        title="Mozilla Firefox",
        wm_class="firefox.Firefox",
        desktop=0,
        gtk_app_id="firefox",
        gtk_unique_bus_name=":1.9",
        gtk_application_object_path="/org/mozilla/Firefox",
    )
    running = app_action_rows(firefox, 6, window_count=1, windows=[firefox_win])
    assert running[0]["synthetic_new_window"] is True


def test_well_known_gtk_muxer_works_without_window_unique_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    settings = SimpleNamespace(
        name="Settings",
        icon="settings",
        app_id="org.gnome.Settings.desktop",
        actions={"launch": {"name": "Launch"}, "action:about": {"name": "About"}},
        single_window=False,
    )
    wayland = WindowInfo(
        wid="0x3",
        title="Settings",
        wm_class="org.gnome.Settings",
        desktop=0,
        app_id="org.gnome.Settings",
    )
    monkeypatch.setattr(apps_mod, "probe_gtk_actions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(apps_mod, "list_gtk_action_names", lambda *_args, **_kwargs: [])
    assert app_is_unique_gtk(settings, [wayland]) is True
    assert app_muxer_has_new_window(settings, [wayland]) is False
    assert can_open_new_window(1, settings, windows=[wayland]) is False
    assert [row["action_name"] for row in app_action_rows(settings, 6, window_count=1, windows=[wayland])] == ["about"]

    monkeypatch.setattr(apps_mod, "probe_gtk_actions", lambda *_args, **_kwargs: ["new-window"])
    monkeypatch.setattr(apps_mod, "list_gtk_action_names", lambda *_args, **_kwargs: ["new-window"])
    assert app_muxer_has_new_window(settings, [wayland]) is True
    assert can_open_new_window(1, settings, windows=[wayland]) is True

    firefox = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        actions={"launch": {"name": "Launch"}},
        single_window=False,
    )
    firefox_win = WindowInfo(wid="0x4", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0)
    monkeypatch.setattr(apps_mod, "probe_gtk_actions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(apps_mod, "list_gtk_action_names", lambda *_args, **_kwargs: [])
    assert app_is_unique_gtk(firefox, [firefox_win]) is False
    assert can_open_new_window(1, firefox, windows=[firefox_win]) is True


def test_muxer_new_window_beats_single_window_and_unique_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    monkeypatch.setattr(apps_mod, "probe_gtk_actions", lambda *_args, **_kwargs: ["new-window"])
    monkeypatch.setattr(apps_mod, "list_gtk_action_names", lambda *_args, **_kwargs: ["new-window"])
    settings = SimpleNamespace(
        name="Settings",
        icon="settings",
        app_id="org.gnome.Settings.desktop",
        actions={"launch": {"name": "Launch"}, "action:about": {"name": "About"}},
        single_window=True,
    )
    unique = WindowInfo(
        wid="0x1",
        title="Settings",
        wm_class="org.gnome.Settings",
        desktop=0,
        gtk_app_id="org.gnome.Settings",
        gtk_unique_bus_name=":1.42",
        gtk_application_object_path="/org/gnome/Settings",
    )
    assert muxer_has_new_window_action(["quit", "app.new-window"]) is True
    assert muxer_has_new_window_action(["about"]) is False
    assert can_open_new_window(1, settings, muxer_new_window=True) is True
    assert can_open_new_window(1, settings, unique_gtk=True, muxer_new_window=True) is True
    rows = app_action_rows(settings, 6, window_count=1, windows=[unique])
    assert rows[0]["synthetic_new_window"] is True
    assert rows[0]["title"] == "New window — Settings"


def test_app_row_description_and_window_count() -> None:
    app = SimpleNamespace(app_id="firefox.desktop", _executable="firefox")
    windows = [
        WindowInfo(wid="1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=1),
        WindowInfo(wid="2", title="Terminal", wm_class="gnome-terminal.Gnome-terminal", desktop=0, pid=2),
        WindowInfo(
            wid="3",
            title="Firefox Hidden",
            wm_class="firefox.Firefox",
            desktop=0,
            pid=1,
            skip_taskbar=True,
        ),
    ]
    assert app_window_count(app, windows) == 2
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
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", lambda _app_id: None)
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
    hidden = [
        WindowInfo(
            wid="0x2",
            title="Firefox Hidden",
            wm_class="Navigator.firefox",
            desktop=0,
            pid=11,
            skip_taskbar=True,
        ),
        WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="Navigator.firefox", desktop=0, pid=11),
    ]
    activated.clear()
    assert focus_open_windows(app, hidden) is True
    assert activated[0]["wid"] == "0x1"
    activated.clear()
    assert focus_open_windows(app, hidden[:1]) is True
    assert activated[0]["wid"] == "0x2"


def test_match_apps_skips_one_bad_desktop_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    class _Bad:
        app_id = "broken.desktop"

        @property
        def name(self) -> str:
            message = "invalid desktop encoding"
            raise RuntimeError(message)

    good = SimpleNamespace(
        name="Notes",
        generic_name="",
        description="",
        app_id="notes.desktop",
        keywords=[],
    )

    class _Rankings:
        def get_app_ids(self) -> list[str]:
            return []

    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [_Bad(), good])
    monkeypatch.setattr(apps_mod.AppRankings, "load", classmethod(lambda _cls: _Rankings()))
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", lambda _app_id: None)
    assert [app.name for app in match_apps("notes")] == ["Notes"]


def test_home_apps_lists_unused_apps_and_collapses_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    esr = SimpleNamespace(name="Firefox ESR", app_id="firefox-esr.desktop")
    stable = SimpleNamespace(name="Firefox", app_id="firefox.desktop")
    notes = SimpleNamespace(name="Notes", app_id="notes.desktop")

    class _Rankings:
        def get_app_ids(self) -> list[str]:
            return ["firefox.desktop"]

    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [esr, notes, stable])
    monkeypatch.setattr(apps_mod.AppRankings, "load", classmethod(lambda _cls: _Rankings()))
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", lambda _app_id: None)
    assert [app.name for app in home_apps(6)] == ["Firefox", "Notes"]
    assert [app.name for app in home_apps(1)] == ["Firefox"]
    assert home_apps(0) == []


def test_home_apps_skips_bad_desktop_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    class _Bad:
        @property
        def app_id(self) -> str:
            message = "invalid desktop encoding"
            raise RuntimeError(message)

    notes = SimpleNamespace(name="Notes", app_id="notes.desktop")

    class _Rankings:
        def get_app_ids(self) -> list[str]:
            return []

    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [_Bad(), notes])
    monkeypatch.setattr(apps_mod.AppRankings, "load", classmethod(lambda _cls: _Rankings()))
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", lambda _app_id: None)
    assert [app.name for app in home_apps(6)] == ["Notes"]


def test_open_new_window_uses_desktop_action_then_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[tuple[str, str | None, bool]] = []

    def _launch(app_id: str, action_name: str | None = None, *, raise_existing: bool = True) -> bool:
        launched.append((app_id, action_name, raise_existing))
        return True

    monkeypatch.setattr("ulauncher.modes.apps.launch_app.launch_app", _launch)
    firefox = SimpleNamespace(
        name="Firefox",
        app_id="firefox.desktop",
        actions={"action:new-window": {"name": "New Window"}},
    )
    assert open_new_window(firefox) is True
    assert launched == [("firefox.desktop", "new-window", True)]
    launched.clear()
    notes = SimpleNamespace(name="Notes", app_id="notes.desktop", actions={"launch": {"name": "Launch"}})
    assert open_new_window(notes) is True
    assert launched == [("notes.desktop", None, False)]


def test_home_apps_prefers_gnome_app_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher import apps as apps_mod

    firefox = SimpleNamespace(name="Firefox", app_id="firefox.desktop")
    notes = SimpleNamespace(name="Notes", app_id="notes.desktop")
    scores = {"notes.desktop": 80.0, "firefox.desktop": 1.0}

    class _Rankings:
        def get_app_ids(self) -> list[str]:
            return ["firefox.desktop"]

    monkeypatch.setattr(apps_mod.AppRankings, "load", classmethod(lambda _cls: _Rankings()))
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", scores.get)
    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [firefox, notes])
    assert [app.name for app in home_apps(6)] == ["Notes", "Firefox"]
    alpha = SimpleNamespace(
        name="Alpha Editor",
        app_id="alpha.desktop",
        generic_name="",
        description="",
        keywords=[],
    )
    beta = SimpleNamespace(
        name="Beta Editor",
        app_id="beta.desktop",
        generic_name="",
        description="",
        keywords=[],
    )
    editor_scores = {"beta.desktop": 80.0, "alpha.desktop": 1.0}
    monkeypatch.setattr(apps_mod, "iter_apps", lambda: [alpha, beta])
    monkeypatch.setattr(apps_mod, "gnome_app_usage_score", editor_scores.get)
    assert [app.name for app in match_apps("editor", 6)] == ["Beta Editor", "Alpha Editor"]
