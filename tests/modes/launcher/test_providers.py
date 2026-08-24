from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.clock import match_clock
from ulauncher.modes.launcher.color import parse_color
from ulauncher.modes.launcher.plan import flags_from_settings, plan_search
from ulauncher.modes.launcher.units import convert_query
from ulauncher.modes.launcher.urls import match_url
from ulauncher.modes.launcher.web import web_result


def _flags(**overrides: object) -> dict:
    settings = SimpleNamespace(
        enable_prefix_modes=True,
        enable_url_open=True,
        enable_path_open=True,
        enable_places=True,
        enable_bookmarks=True,
        enable_application_mode=True,
        enable_calculator=True,
        enable_unit_convert=True,
        enable_color_hex=True,
        enable_time_date=True,
        enable_window_search=True,
        enable_system_actions=True,
        enable_settings_search=True,
        enable_recent_files=True,
        enable_command_run=False,
        show_web_search=True,
        result_order="default",
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return flags_from_settings(settings)


def test_web_is_not_forced_when_url_matches() -> None:
    planned = plan_search("example.com", _flags())
    assert "url" in planned["providers"]
    assert planned["web_fallback"] is True
    assert match_url("example.com") is not None


def test_at_prefix_plans_web_only() -> None:
    planned = plan_search("@ ulauncher", _flags())
    assert planned["mode"] == "web"
    assert planned["providers"] == ["web"]
    assert planned["web_fallback"] is False
    hit = web_result("ulauncher", "google")
    assert "ulauncher" in hit["url"]
    assert hit["title"] == 'Search Google for "ulauncher"'
    assert hit["description"] == "Open Google in your browser"
    assert hit["icon"] == "web-browser-symbolic"


def test_color_hex_parses() -> None:
    hit = parse_color("#ff0000")
    assert hit is not None
    assert hit["hex"] == "#ff0000"
    assert hit["r"] == 255


def test_clock_time_query() -> None:
    hit = match_clock("time")
    assert hit is not None
    assert "time" in hit


def test_unit_conversion() -> None:
    hit = convert_query("10 km to mi")
    assert hit is not None
    assert "mi" in hit["title"]
    spoken = convert_query("ten km to mi")
    assert spoken is not None
    assert spoken["copy_text"] == hit["copy_text"]


def test_color_requires_hash() -> None:
    assert parse_color("#ff0000") is not None
    assert parse_color("ff0000") is None
