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
    url = next(row for row in _handle("example.com") if getattr(row, "kind", "") == "url")
    assert url.name == "https://example.com"


def test_empty_at_prefix_has_no_web_row() -> None:
    assert _kinds(_handle("@")) == []
    assert _kinds(_handle("@ ")) == []


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


def test_hash_prefix_honors_max_per_category(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.max_per_category = 8
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    rows = [row for row in _handle("#") if getattr(row, "kind", "") == "settings"]
    assert len(rows) == 8


def test_settings_and_system_search_pass_max_per_category(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.settings_panels import settings_panel_available
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.max_per_category = 8
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    seen: dict[str, object] = {}
    wifi = {"id": "wifi", "title": "Wi-Fi", "icon": "network-wireless-symbolic", "keywords": []}

    def fake_settings(_query: str, limit: int = 6, is_available: object = None) -> list:
        seen["settings_limit"] = limit
        seen["settings_available"] = is_available
        return [wifi]

    def fake_system(_query: str, limit: int = 6, **_kwargs: object) -> list:
        seen["system_limit"] = limit
        return [{"id": "lock", "title": "Lock Screen", "icon": "system-lock-screen-symbolic"}]

    monkeypatch.setattr("ulauncher.modes.launcher.settings_panels.match_settings_panels", fake_settings)
    monkeypatch.setattr("ulauncher.modes.launcher.system_actions.match_system_actions", fake_system)
    _handle("#")
    assert seen["settings_limit"] == 8
    assert seen["settings_available"] is settings_panel_available
    _handle("lock the screen")
    assert seen["system_limit"] == 8


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
    assert window.icon == "firefox"
    assert window.payload.get("app_id") == "firefox"
    assert window.payload.get("window_title") == "Mozilla Firefox"
    assert app.description == "Switch to application"


def test_empty_state_window_icon_uses_installed_app_outside_home_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    firefox = SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop", _executable="firefox")
    terminal = SimpleNamespace(name="Terminal", icon="utilities-terminal", app_id="org.gnome.Terminal.desktop")
    _patch_empty_state(
        monkeypatch,
        settings,
        [terminal],
        [
            WindowInfo(
                wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11, app_id="firefox"
            )
        ],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.apps.iter_apps", lambda: [firefox, terminal])
    results = list(LauncherMode().get_home_results(6))
    window = next(row for row in results if row.kind == "window")
    assert window.icon == "firefox"
    assert window.payload["app_id"] == "firefox"


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


def test_empty_state_isolates_windows_from_frequent_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "spotlight"
    settings.applied_look = "spotlight"
    settings.result_order = "default"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True

    def boom_apps(_limit: int) -> list:
        msg = "desktop list failed"
        raise RuntimeError(msg)

    _patch_empty_state(
        monkeypatch,
        settings,
        [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")],
        [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.apps.home_apps", boom_apps)
    results = list(LauncherMode().get_home_results(6))
    assert _kinds(results) == ["window"]

    def boom_windows() -> list:
        msg = "window list failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        "ulauncher.modes.launcher.apps.home_apps",
        lambda limit: [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")][:limit],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows.cached_windows", boom_windows)
    results = list(LauncherMode().get_home_results(6))
    assert _kinds(results) == ["app"]


def test_empty_state_skips_one_vanished_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    class Vanished:
        wid = "0xbad"
        wm_class = "gone"
        desktop = 0
        pid = 1
        sticky = False

        @property
        def title(self) -> str:
            msg = "window closed"
            raise RuntimeError(msg)

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    _patch_empty_state(
        monkeypatch,
        settings,
        [SimpleNamespace(name="Notes", icon="notes", app_id="notes.desktop")],
        [
            Vanished(),
            WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11),
        ],
    )
    results = list(LauncherMode().get_home_results(6))
    assert _kinds(results) == ["window", "app"]
    assert [row.name for row in results] == ["Mozilla Firefox", "Notes"]


def test_empty_state_hides_skip_taskbar_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    _patch_empty_state(
        monkeypatch,
        settings,
        [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")],
        [
            WindowInfo(
                wid="0x2",
                title="Top Bar",
                wm_class="firefox.Firefox",
                desktop=0,
                pid=11,
                skip_taskbar=True,
            ),
            WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11),
        ],
    )
    capped = list(LauncherMode().get_home_results(1))
    assert [row.name for row in capped] == ["Mozilla Firefox"]
    results = list(LauncherMode().get_home_results(6))
    kinds = _kinds(results)
    assert kinds[0] == "window"
    assert [row.name for row in results if row.kind == "window"] == ["Mozilla Firefox"]
    app = next(row for row in results if row.kind == "app")
    assert app.description == "Switch to application"


def test_settings_row_copy_matches_goshos() -> None:
    results = _handle("# wifi")
    settings_row = next(row for row in results if getattr(row, "kind", "") == "settings")
    assert settings_row.description == "GNOME Settings"


def test_settings_without_launcher_are_not_activatable(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.settings_panels import settings_result_meta

    monkeypatch.setattr(
        "ulauncher.modes.launcher.settings_panels.settings_argv",
        lambda *_a, **_k: None,
    )
    wifi = next(row for row in _handle("# wifi") if getattr(row, "kind", "") == "settings")
    assert wifi.name == "Wi-Fi"
    assert wifi.activatable is False
    assert wifi.actions == {}
    panel = {"id": "wifi", "title": "Wi-Fi", "icon": "network-wireless-symbolic", "keywords": []}
    assert settings_result_meta(panel, None)["activatable"] is False


def test_clock_and_units_copy_prompt_enter() -> None:
    clock = next(row for row in _handle("time") if getattr(row, "kind", "") == "clock")
    assert clock.description.endswith(" · press Enter to copy")
    units = next(row for row in _handle("10 km to mi") if getattr(row, "kind", "") == "units")
    assert units.description.endswith(" · press Enter to copy")
    assert "system" in _kinds(_handle("lock the screen"))
    assert "units" in _kinds(_handle("convert 10 km to mi"))
    assert "calculator" in _kinds(_handle("half of 80"))


def test_places_rows_keep_folder_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ulauncher.modes.launcher.paths.terminal_command",
        lambda directory, **_kwargs: {"argv": ["xdg-terminal-exec"], "cwd": directory},
    )
    results = _handle("docs")
    places = [row for row in results if getattr(row, "kind", "") == "place"]
    assert places
    docs = next(row for row in places if row.name == "Documents")
    assert docs.description
    assert docs.icon == "folder-documents-symbolic"
    term = next(row for row in places if row.name == "Open in Terminal")
    assert term.kind == "place"


def test_compact_density_still_shows_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.look_id = "krunner"
    settings.applied_look = "krunner"
    settings.row_density = "compact"
    settings.show_descriptions = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    calc = next(row for row in _handle("2+2") if getattr(row, "kind", "") == "calculator")
    assert calc.description
    assert calc.compact is False


def test_path_query_returns_path_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ulauncher.modes.launcher.paths.terminal_command",
        lambda directory, **_kwargs: {"argv": ["xdg-terminal-exec"], "cwd": directory},
    )
    results = _handle("/tmp")
    assert "path" in _kinds(results)
    assert any(row.name == "Open in Terminal" for row in results)
    missing = [row for row in _handle("/no/such/goshlauncher/path-xyz") if getattr(row, "kind", "") == "path"]
    assert any(row.description == "Path not found" for row in missing)


def test_path_first_paint_is_checking_until_flush() -> None:
    captured: list = []
    mode = LauncherMode()
    mode.handle_query(Query(None, "/tmp"), captured.append)
    assert captured
    first = captured[0]["results"]
    path = next(row for row in first if getattr(row, "kind", "") == "path")
    assert path.description == "Checking path"
    assert path.activatable is False
    mode.flush_lookups()
    last = captured[-1]["results"]
    path = next(row for row in last if getattr(row, "kind", "") == "path" and not row.payload.get("in_terminal"))
    assert path.description == "Open path"
    assert path.activatable is True


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


def test_close_window_row_keeps_muxer_and_atspi_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_window_search = True
    settings.enable_application_mode = False
    settings.enable_calculator = False
    settings.enable_unit_convert = False
    settings.enable_color_hex = False
    settings.enable_time_date = False
    settings.show_web_search = False
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.match_windows",
        lambda _query, _limit: [
            {
                "kind": "close",
                "title": "Close Mozilla Firefox",
                "window_title": "Mozilla Firefox",
                "description": "Workspace 1",
                "icon": "firefox",
                "wid": "ext:abc",
                "pid": 0,
                "wm_class": "firefox",
                "app_id": "firefox",
                "gtk_unique_bus_name": ":1.9",
                "gtk_application_object_path": "/org/mozilla/firefox",
                "atspi_ref": "bus\0/w/1",
                "payload": "ext:abc",
                "id": "close-firefox",
            }
        ],
    )
    row = next(result for result in _handle("close firefox") if getattr(result, "kind", "") == "window-close")
    assert row.icon == "firefox"
    assert row.payload["kind"] == "close"
    assert row.payload["window_title"] == "Mozilla Firefox"
    assert row.payload["atspi_ref"] == "bus\0/w/1"
    assert row.payload["gtk_unique_bus_name"] == ":1.9"
    assert row.payload["app_id"] == "firefox"


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


def test_running_app_offers_new_window_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_app_actions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    app = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        _executable="firefox",
        actions={
            "launch": {"name": "Launch"},
            "action:new-window": {"name": "New Window"},
            "action:private": {"name": "Private"},
        },
    )
    monkeypatch.setattr("ulauncher.modes.launcher.apps.match_apps", lambda _query, _limit: [app])
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.cached_windows",
        lambda: [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None)
    results = _handle("open firefox")
    kinds = _kinds(results)
    assert "app" in kinds
    assert "app-action" in kinds
    assert "window" in kinds
    assert any(row.name == "New window — Firefox" for row in results)
    assert any(row.name == "Private — Firefox" for row in results)
    assert any(row.name == "Applications" for row in results)
    assert any(row.description == "Switch to application" for row in results)


def _stub_typed_firefox(monkeypatch: pytest.MonkeyPatch, settings: object) -> None:
    from ulauncher.utils.settings import Settings

    app = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        _executable="firefox",
        actions={"launch": {"name": "Launch"}, "action:private": {"name": "Private"}},
    )
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr("ulauncher.modes.launcher.apps.match_apps", lambda _query, _limit: [app])
    monkeypatch.setattr("ulauncher.modes.launcher.windows.cached_windows", list)
    monkeypatch.setattr("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None)
    monkeypatch.setattr("ulauncher.modes.launcher.windows.match_windows", lambda *_args, **_kwargs: [])


def test_throwing_url_provider_still_shows_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_application_mode = True
    _stub_typed_firefox(monkeypatch, settings)

    def boom(_query: str) -> None:
        message = "url vanished"
        raise RuntimeError(message)

    monkeypatch.setattr("ulauncher.modes.launcher.urls.match_url", boom)
    assert "app" in _kinds(_handle("firefox"))


def test_throwing_window_list_still_shows_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_application_mode = True
    settings.enable_window_search = True
    _stub_typed_firefox(monkeypatch, settings)

    def boom() -> list:
        message = "windows vanished"
        raise RuntimeError(message)

    monkeypatch.setattr("ulauncher.modes.launcher.windows.cached_windows", boom)
    kinds = _kinds(_handle("firefox"))
    assert "app" in kinds
    assert "app-action" in kinds


def test_throwing_app_actions_keep_app_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_application_mode = True
    settings.enable_app_actions = True
    _stub_typed_firefox(monkeypatch, settings)

    def boom(*_args: object, **_kwargs: object) -> list:
        message = "actions vanished"
        raise RuntimeError(message)

    monkeypatch.setattr("ulauncher.modes.launcher.apps.app_action_rows", boom)
    kinds = _kinds(_handle("firefox"))
    assert "app" in kinds
    assert "app-action" not in kinds


def test_throwing_apps_still_show_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.enable_application_mode = True
    settings.enable_window_search = True
    settings.show_web_search = False
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))

    def boom(_query: str, _limit: int) -> list:
        message = "apps vanished"
        raise RuntimeError(message)

    monkeypatch.setattr("ulauncher.modes.launcher.apps.match_apps", boom)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.match_windows",
        lambda _query, _limit: [
            {
                "title": "Mozilla Firefox",
                "description": "Workspace 1",
                "icon": "firefox",
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
    assert "window" in _kinds(_handle("firefox"))
    assert "app" not in _kinds(_handle("firefox"))


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


def test_units_color_and_clock_copy_the_row_title(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "ulauncher.modes.launcher.mode._events.emit",
        lambda name, data: seen.append((name, str(data))),
    )
    cases = (("10 km to mi", "units"), ("red", "color"), ("time", "clock"))
    for query, kind in cases:
        seen.clear()
        result = next(row for row in _handle(query) if getattr(row, "kind", "") == kind)
        captured: list = []
        LauncherMode().activate_result("activate", result, Query(None, query), captured.append)
        assert seen == [("app:copy_and_close", result.name)]
        assert captured[-1]["type"] == EffectType.CLOSE_WINDOW
