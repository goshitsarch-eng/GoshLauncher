from __future__ import annotations

from ulauncher.internals.effects import EffectType
from ulauncher.internals.query import Query
from ulauncher.modes.launcher.mode import LauncherMode
from ulauncher.modes.launcher.results import LauncherResult


def test_matches_almost_everything_except_paths() -> None:
    mode = LauncherMode()
    assert mode.matches_query_str("firefox")
    assert mode.matches_query_str("=1+2")
    assert mode.matches_query_str("$ firefox")
    assert not mode.matches_query_str("")
    assert not mode.matches_query_str("~/Downloads")
    assert not mode.matches_query_str("/usr")


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
