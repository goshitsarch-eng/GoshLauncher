from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ulauncher.internals.effects import EffectType
from ulauncher.internals.query import Query
from ulauncher.modes.launcher.mode import LauncherMode
from ulauncher.modes.launcher.results import LauncherResult


def test_matches_any_non_empty_query() -> None:
    mode = LauncherMode()
    assert mode.matches_query_str("firefox")
    assert mode.matches_query_str("=1+2")
    assert mode.matches_query_str("$ firefox")
    assert mode.matches_query_str("~/Downloads")
    assert mode.matches_query_str("/usr")
    assert mode.matches_query_str("./bin")
    assert not mode.matches_query_str("")


def test_launcher_result_has_activate_action() -> None:
    result = LauncherResult(name="Test", kind="app", payload={"app_id": "x.desktop"})
    assert "activate" in result.actions
    assert result.highlightable is True


def _handle(query: str) -> list:
    captured: list = []
    mode = LauncherMode()
    mode.handle_query(Query(None, query), captured.append)
    mode.flush_lookups()
    assert captured
    message = captured[-1]
    assert message["type"] == EffectType.RENDER_RESULTS
    return list(message["results"])


def _kinds(results: list) -> list[str]:
    return [str(getattr(row, "kind", "")) for row in results if getattr(row, "kind", "")]


def test_url_query_does_not_force_web() -> None:
    kinds = _kinds(_handle("example.com"))
    assert "url" in kinds
    assert "web" not in kinds


def test_at_prefix_is_web() -> None:
    kinds = _kinds(_handle("@ cats"))
    assert kinds == ["web"]


def test_equals_prefix_is_calculator() -> None:
    results = _handle("=42")
    kinds = _kinds(results)
    assert "calculator" in kinds
    calc = next(row for row in results if getattr(row, "kind", "") == "calculator")
    assert calc.name == "42"


def test_bare_number_is_not_calculator_only() -> None:
    kinds = _kinds(_handle("42"))
    assert "calculator" not in kinds


def test_hash_wifi_is_settings_not_color() -> None:
    kinds = _kinds(_handle("# wifi"))
    assert "settings" in kinds
    assert "color" not in kinds


def test_hex_color_without_space() -> None:
    kinds = _kinds(_handle("#ff0000"))
    assert "color" in kinds
    assert "settings" not in kinds


def test_modern_css_color_query() -> None:
    results = _handle("hsl(0deg 100% 50%)")
    kinds = _kinds(results)
    assert "color" in kinds
    color = next(row for row in results if getattr(row, "kind", "") == "color")
    assert color.name == "#ff0000"
    assert color.description == "Press Enter to copy color"
    kinds = _kinds(_handle("rgb(255 0 0)"))
    assert "color" in kinds
    kinds = _kinds(_handle("hwb(0 0% 0%)"))
    assert "color" in kinds


def test_spoken_math_and_units() -> None:
    kinds = _kinds(_handle("two plus two"))
    assert "calculator" in kinds
    kinds = _kinds(_handle("what is 2+2"))
    assert "calculator" in kinds
    kinds = _kinds(_handle("10 km to mi"))
    assert "units" in kinds


def test_bare_hex_is_not_forced_color() -> None:
    kinds = _kinds(_handle("ff0000"))
    assert "color" not in kinds


def test_command_prefix_always_shows_a_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_command_run = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    results = _handle("! definitely-not-a-ulauncher-binary-xyz")
    kinds = _kinds(results)
    assert "command" in kinds
    command = next(row for row in results if getattr(row, "kind", "") == "command")
    assert command.description == "Command not found"
    assert command.payload.get("ready") is False
    assert command.actions == {}


def test_clock_query_uses_title_fields() -> None:
    results = _handle("time")
    kinds = _kinds(results)
    assert "clock" in kinds
    clock = next(row for row in results if getattr(row, "kind", "") == "clock")
    assert clock.payload.get("copy_text") == clock.name


def test_command_row_includes_home_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_command_run = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    binary = "/usr/bin/true" if Path("/usr/bin/true").is_file() else "/usr/bin/python3"
    results = _handle(f"! {binary}")
    command = next(row for row in results if getattr(row, "kind", "") == "command")
    assert command.payload.get("ready") is True
    assert command.payload.get("cwd") == str(Path.home())


def test_empty_state_puts_windows_first_for_popos(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr(
        "ulauncher.modes.launcher.apps.home_apps",
        lambda limit: [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")][:limit],
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.cached_windows",
        lambda: [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None)
    results = list(LauncherMode().get_home_results(6))
    kinds = _kinds(results)
    assert kinds[:2] == ["window", "app"]
    window = next(row for row in results if row.kind == "window")
    app = next(row for row in results if row.kind == "app")
    assert window.description == "Workspace 1"
    assert window.icon == "focus-windows-symbolic"
    assert app.description == "Switch to application"


def _patch_empty_state(
    monkeypatch: pytest.MonkeyPatch,
    settings: object,
    apps: list,
    windows: list,
) -> None:
    from ulauncher.utils.settings import Settings

    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr("ulauncher.modes.launcher.apps.home_apps", lambda limit: apps[:limit])
    monkeypatch.setattr("ulauncher.modes.launcher.windows.cached_windows", lambda: windows)
    monkeypatch.setattr("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None)


def test_empty_state_hides_apps_when_apps_are_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = False
    settings.enable_window_search = True
    _patch_empty_state(
        monkeypatch,
        settings,
        [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")],
        [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    results = list(LauncherMode().get_home_results(6))
    assert _kinds(results) == ["window"]


def test_empty_state_ignores_legacy_recent_app_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    settings.max_recent_apps = 0
    _patch_empty_state(
        monkeypatch,
        settings,
        [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")],
        [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    results = list(LauncherMode().get_home_results(6))
    assert _kinds(results) == ["window", "app"]


def test_empty_state_honors_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    apps = [SimpleNamespace(name=f"App{i}", icon="app", app_id=f"app{i}.desktop") for i in range(1, 5)]
    windows = [WindowInfo(wid=f"0x{i}", title=f"Win{i}", wm_class="x.X", desktop=0, pid=i) for i in range(1, 5)]
    _patch_empty_state(monkeypatch, settings, apps, windows)
    results = list(LauncherMode().get_home_results(2))
    assert _kinds(results) == ["window", "window"]
    assert [row.name for row in results] == ["Win1", "Win2"]

    settings.look_id = "spotlight"
    settings.applied_look = "spotlight"
    settings.result_order = "default"
    results = list(LauncherMode().get_home_results(2))
    assert _kinds(results) == ["app", "app"]
    assert [row.name for row in results] == ["App1", "App2"]


def test_empty_suggestions_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_empty_suggestions = False
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    assert list(LauncherMode().get_home_results(6)) == []


def test_settings_row_copy_matches_goshos() -> None:
    results = _handle("# wifi")
    settings_row = next(row for row in results if getattr(row, "kind", "") == "settings")
    assert settings_row.description == "GNOME Settings"


def test_clock_and_units_copy_prompt_enter() -> None:
    clock = next(row for row in _handle("time") if getattr(row, "kind", "") == "clock")
    assert clock.description.endswith(" · press Enter to copy")
    units = next(row for row in _handle("10 km to mi") if getattr(row, "kind", "") == "units")
    assert units.description.endswith(" · press Enter to copy")
    assert "system" in _kinds(_handle("lock the screen"))
    assert "units" in _kinds(_handle("convert 10 km to mi"))
    assert "calculator" in _kinds(_handle("half of 80"))


def test_path_query_returns_path_results() -> None:
    kinds = _kinds(_handle("/tmp"))
    assert "path" in kinds


def test_path_first_paint_is_checking_until_flush() -> None:
    captured: list = []
    mode = LauncherMode()
    mode.handle_query(Query(None, "/tmp"), captured.append)
    assert captured
    first = captured[0]["results"]
    path = next(row for row in first if getattr(row, "kind", "") == "path")
    assert path.description == "Checking path"
    mode.flush_lookups()
    last = captured[-1]["results"]
    path = next(row for row in last if getattr(row, "kind", "") == "path" and not row.payload.get("in_terminal"))
    assert path.description == "Open path"


def test_bookmark_first_paint_empty_until_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bookmark_file = tmp_path / "bookmarks"
    bookmark_file.write_text("file:///tmp UniqueBookmarkLabelXYZ\n", encoding="utf-8")
    monkeypatch.setattr("ulauncher.modes.launcher.bookmarks.BOOKMARK_FILES", (bookmark_file,))
    from ulauncher.modes.launcher.bookmarks import invalidate_bookmarks

    invalidate_bookmarks()
    captured: list = []
    mode = LauncherMode()
    mode.handle_query(Query(None, "UniqueBookmarkLabelXYZ"), captured.append)
    assert captured
    first_kinds = [str(getattr(row, "kind", "")) for row in captured[0]["results"]]
    assert "bookmark" not in first_kinds
    mode.flush_lookups()
    last_kinds = [str(getattr(row, "kind", "")) for row in captured[-1]["results"]]
    assert "bookmark" in last_kinds


def test_search_order_windows_first_puts_windows_before_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.result_order = "windows-first"
    settings.enable_application_mode = True
    settings.enable_window_search = True
    settings.enable_app_actions = False
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr(
        "ulauncher.modes.launcher.apps.match_apps",
        lambda _query, _limit: [
            SimpleNamespace(
                name="Firefox",
                icon="firefox",
                app_id="firefox.desktop",
                actions={"launch": {"name": "Launch"}},
            )
        ],
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.match_windows",
        lambda _query, _limit: [
            {
                "title": "Mozilla Firefox",
                "description": "Workspace 1",
                "icon": "focus-windows-symbolic",
                "wid": "0x1",
                "pid": 11,
                "wm_class": "firefox",
                "kind": "focus",
                "payload": "0x1",
            }
        ],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows.cached_windows", list)
    monkeypatch.setattr("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None)
    kinds = _kinds(_handle("fire"))
    assert "window" in kinds
    assert "app" in kinds
    assert kinds.index("window") < kinds.index("app")


def test_get_modes_launcher_owns_typed_search() -> None:
    from ulauncher.core import get_modes

    get_modes.cache_clear()
    names = [type(mode).__name__ for mode in get_modes()]
    assert names[0] == "LauncherMode"
    assert "FileBrowserMode" not in names
    assert "CalcMode" not in names
    assert "ShortcutMode" in names
    assert "ExtensionMode" in names
    assert "AppMode" in names


def test_web_fallback_when_nothing_local_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.show_web_search = True
    for attr in (
        "enable_application_mode",
        "enable_url_open",
        "enable_path_open",
        "enable_places",
        "enable_bookmarks",
        "enable_calculator",
        "enable_unit_convert",
        "enable_color_hex",
        "enable_time_date",
        "enable_window_search",
        "enable_system_actions",
        "enable_settings_search",
        "enable_recent_files",
        "enable_command_run",
    ):
        setattr(settings, attr, False)
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    results = _handle("zzzxqwerty999nomatch")
    assert _kinds(results) == ["web"]
    web = next(row for row in results if getattr(row, "kind", "") == "web")
    assert web.payload["url"].startswith("https://www.google.com/search?q=")
    assert "zzzxqwerty999nomatch" in web.payload["url"]


def test_at_prefix_still_searches_when_web_fallback_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.show_web_search = False
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    kinds = _kinds(_handle("@ cats"))
    assert kinds == ["web"]
    kinds = _kinds(_handle("zzzxqwerty999nomatch"))
    assert "web" not in kinds


def test_javascript_alert_is_not_a_url() -> None:
    kinds = _kinds(_handle("javascript:alert(1)"))
    assert "url" not in kinds


def test_mailto_and_localhost_are_urls() -> None:
    assert "url" in _kinds(_handle("mailto:nin@example.com"))
    assert "url" in _kinds(_handle("localhost:3000"))
    assert "url" not in _kinds(_handle("https://example.com/foo bar"))


def test_calculator_activate_copies_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ulauncher.modes.launcher.mode._events.emit",
        lambda name, data: seen.append((name, str(data))),
    )
    result = next(row for row in _handle("2+2") if getattr(row, "kind", "") == "calculator")
    captured: list = []
    LauncherMode().activate_result("activate", result, Query(None, "2+2"), captured.append)
    assert seen == [("app:copy_and_close", "4")]
    assert captured[-1]["type"] == EffectType.CLOSE_WINDOW
