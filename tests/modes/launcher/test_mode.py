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
    LauncherMode().handle_query(Query(None, query), captured.append)
    assert captured
    message = captured[0]
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


def test_spoken_math_and_units() -> None:
    kinds = _kinds(_handle("two plus two"))
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
        "ulauncher.modes.launcher.windows.list_windows",
        lambda: [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)],
    )
    results = list(LauncherMode().get_home_results(6))
    kinds = _kinds(results)
    assert kinds[:2] == ["window", "app"]
    window = next(row for row in results if row.kind == "window")
    app = next(row for row in results if row.kind == "app")
    assert window.description == "Workspace 1"
    assert app.description == "Switch to application"


def test_spoken_system_and_unit_queries() -> None:
    assert "system" in _kinds(_handle("lock the screen"))
    assert "units" in _kinds(_handle("convert 10 km to mi"))
    assert "calculator" in _kinds(_handle("half of 80"))


def test_path_query_returns_path_results() -> None:
    kinds = _kinds(_handle("/tmp"))
    assert "path" in kinds


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
                "icon": "focus-windows",
                "wid": "0x1",
                "pid": 11,
                "wm_class": "firefox",
                "kind": "focus",
                "payload": "0x1",
            }
        ],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows.list_windows", list)
    kinds = _kinds(_handle("fire"))
    assert "window" in kinds
    assert "app" in kinds
    assert kinds.index("window") < kinds.index("app")
