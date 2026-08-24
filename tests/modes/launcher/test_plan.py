from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.plan import flags_from_settings, merge_empty_suggestions, plan_search


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


def test_bare_number_is_not_forced_calculator() -> None:
    planned = plan_search("42", _flags())
    assert planned["mode"] == "all"
    assert "calculator" in planned["providers"]
    assert planned["web_fallback"] is True


def test_equals_prefix_is_calculator_only() -> None:
    planned = plan_search("=42", _flags())
    assert planned["mode"] == "calculator"
    assert planned["providers"] == ["calculator"]
    assert planned["web_fallback"] is False


def test_at_prefix_is_web_only() -> None:
    planned = plan_search("@ cats", _flags())
    assert planned["mode"] == "web"
    assert planned["providers"] == ["web"]


def test_command_prefix_respects_flag() -> None:
    assert plan_search("! ls", _flags(enable_command_run=False))["providers"] == []
    assert plan_search("! ls", _flags(enable_command_run=True))["providers"] == ["command"]


def test_windows_first_order() -> None:
    planned = plan_search("firefox", _flags(result_order="windows-first"))
    windows = planned["providers"].index("windows")
    apps = planned["providers"].index("apps")
    assert windows < apps


def test_merge_empty_suggestions_windows_first() -> None:
    merged = merge_empty_suggestions("windows-first", ["w1", "w2"], ["a1"], 3)
    assert merged == ["w1", "w2", "a1"]
    merged_apps = merge_empty_suggestions("default", ["w1"], ["a1", "a2"], 2)
    assert merged_apps == ["a1", "a2"]


def test_spoken_open_firefox_strips_verb() -> None:
    from ulauncher.modes.launcher.plan import strip_leading_verb

    assert strip_leading_verb("open firefox") == "firefox"
    assert strip_leading_verb("please open firefox") == "firefox"
    assert strip_leading_verb("open source") == "open source"
    assert strip_leading_verb("find windows firefox") == "firefox"
