from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.plan import (
    flags_from_settings,
    merge_empty_suggestions,
    plan_search,
    should_refresh_bookmarks,
    should_refresh_command,
    should_refresh_path,
    should_refresh_recent_files,
    should_refresh_windows,
)


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
    empty = plan_search("@", _flags())
    assert empty["query"] == ""
    assert empty["providers"] == ["web"]


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
    assert merge_empty_suggestions("default", ["w"], ["a"], 6) == ["a", "w"]
    assert merge_empty_suggestions("windows-first", ["w"], ["a"], 6) == ["w", "a"]
    assert merge_empty_suggestions("windows-first", ["w1", "w2"], ["a1", "a2"], 2) == ["w1", "w2"]
    assert merge_empty_suggestions("default", ["w1"], ["a1"], 0) == []


def test_should_refresh_path_only_for_path_queries() -> None:
    planned = plan_search("/tmp", _flags())
    assert should_refresh_path(True, planned) is True
    planned = plan_search("firefox", _flags())
    assert should_refresh_path(True, planned) is False
    assert should_refresh_path(False, plan_search("/tmp", _flags())) is False


def test_should_refresh_command_only_in_bang_mode() -> None:
    planned = plan_search("! ls", _flags(enable_command_run=True))
    assert should_refresh_command(True, planned) is True
    planned = plan_search("ls", _flags(enable_command_run=True))
    assert should_refresh_command(True, planned) is False


def test_should_refresh_bookmarks_only_in_all_mode() -> None:
    planned = plan_search("docs", _flags())
    assert should_refresh_bookmarks(True, planned) is True
    planned = plan_search("=42", _flags())
    assert should_refresh_bookmarks(True, planned) is False
    assert should_refresh_bookmarks(False, plan_search("docs", _flags())) is False


def test_should_refresh_windows_for_apps_and_window_providers() -> None:
    planned = plan_search("firefox", _flags())
    assert should_refresh_windows(True, True, planned) is True
    assert should_refresh_windows(True, False, planned) is True
    assert should_refresh_windows(False, True, planned) is True
    assert should_refresh_windows(False, False, planned) is False
    planned = plan_search("@ firefox", _flags())
    assert should_refresh_windows(True, True, planned) is False
    planned = plan_search("$ firefox", _flags())
    assert should_refresh_windows(True, False, planned) is True
    assert should_refresh_windows(False, True, planned) is False


def test_should_refresh_recent_files_for_dot_prefix_and_all() -> None:
    planned = plan_search(". notes", _flags())
    assert should_refresh_recent_files(True, planned) is True
    planned = plan_search("notes", _flags())
    assert should_refresh_recent_files(True, planned) is True
    planned = plan_search("@ notes", _flags())
    assert should_refresh_recent_files(True, planned) is False
    assert should_refresh_recent_files(False, plan_search(". notes", _flags())) is False
    lone = plan_search(".", _flags())
    assert lone["mode"] == "files"
    assert lone["query"] == ""
    assert lone["providers"] == ["files"]
    assert should_refresh_recent_files(True, lone) is True
    windows = plan_search("$", _flags())
    assert windows["query"] == ""
    assert windows["providers"] == ["windows"]
    assert should_refresh_windows(True, False, windows) is True


def test_spoken_open_firefox_strips_verb() -> None:
    from ulauncher.modes.launcher.plan import strip_leading_verb

    assert strip_leading_verb("open firefox") == "firefox"
    assert strip_leading_verb("please open firefox") == "firefox"
    assert strip_leading_verb("open source") == "open source"
    assert strip_leading_verb("find windows firefox") == "firefox"
    assert strip_leading_verb("can you close firefox") == "close firefox"
    assert strip_leading_verb("would you please open firefox") == "firefox"
    assert strip_leading_verb("what is 2+2") == "2+2"
    assert strip_leading_verb("what's 2+2") == "2+2"
    assert strip_leading_verb("convert 10 km to mi") == "10 km to mi"
    assert strip_leading_verb("how much is 10 km to mi") == "10 km to mi"
    assert strip_leading_verb("show me the time") == "time"
    assert strip_leading_verb("tell me the time") == "time"
    assert strip_leading_verb("open the pictures folder") == "pictures"
    assert strip_leading_verb("open wifi settings") == "wifi"
    assert strip_leading_verb("open source") == "open source"
    assert strip_leading_verb("open office") == "open office"
    assert strip_leading_verb("open vpn") == "open vpn"
    assert strip_leading_verb("fire up steam") == "steam"
    assert strip_leading_verb("the") == "the"
    assert strip_leading_verb("can you") == "can you"


def test_goshos_spoken_verbs_battery() -> None:
    from ulauncher.modes.launcher.plan import strip_leading_verb

    expected = (
        ("please lock", "lock"),
        ("could you launch gimp", "gimp"),
        ("can you please open firefox", "firefox"),
        ("please can you open firefox", "firefox"),
        ("will you open firefox", "firefox"),
        ("what is the time", "time"),
        ("calculate 2+2", "2+2"),
        ("please convert 10 km to mi", "10 km to mi"),
        ("show me firefox", "firefox"),
        ("can you tell me the time", "time"),
        ("please tell me the date", "date"),
        ("tell me firefox", "firefox"),
        ("my downloads", "downloads"),
        ("open the", "the"),
        ("launch code", "code"),
        ("go to downloads", "downloads"),
        ("find firefox", "firefox"),
        ("search for wifi", "wifi"),
        ("look up hex", "hex"),
        ("lookup hex", "hex"),
        ("help me open firefox", "firefox"),
        ("just open firefox", "firefox"),
        ("i want to open firefox", "firefox"),
        ("navigate to downloads", "downloads"),
        ("navigate to wifi settings", "wifi"),
        ("help me", "help me"),
        ("just", "just"),
        ("search settings wifi", "wifi"),
        ("launch firefox", "firefox"),
        ("run firefox", "firefox"),
        ("start firefox", "firefox"),
        ("open up firefox", "firefox"),
        ("start up firefox", "firefox"),
        ("execute firefox", "firefox"),
        ("search for firefox", "firefox"),
        ("open display preferences", "display"),
        ("open my documents folder", "documents"),
        ("find files notes", "notes"),
        ("search for app firefox", "firefox"),
        ("windows", "windows"),
        ("folder", "folder"),
        ("search for open source", "open source"),
        ("please open source", "open source"),
        ("open up terminal", "terminal"),
        ("execute vscode", "vscode"),
        ("run steam", "steam"),
        ("launch up code", "code"),
        ("open", "open"),
    )
    for query, stripped in expected:
        assert strip_leading_verb(query) == stripped, query


def test_goshos_plan_search_battery() -> None:
    from ulauncher.modes.launcher.calculator import evaluate_arithmetic
    from ulauncher.modes.launcher.clock import time_query_kind

    all_on = _flags()
    assert plan_search("=2+2", all_on)["mode"] == "calculator"
    assert plan_search("=2+2", all_on)["providers"] == ["calculator"]
    assert plan_search("@cats", all_on)["providers"] == ["web"]
    no_web = _flags(show_web_search=False)
    assert plan_search("@cats", no_web)["providers"] == ["web"]
    assert plan_search("chrome", no_web)["web_fallback"] is False
    assert plan_search("", all_on)["providers"] == []
    assert plan_search("   ", all_on)["web_fallback"] is False
    assert plan_search("$", all_on)["providers"] == ["windows"]
    assert plan_search("#", all_on)["providers"] == ["settings"]
    assert plan_search("=2+2", _flags(enable_calculator=False))["providers"] == []
    assert plan_search("=2+2", _flags(enable_prefix_modes=False))["mode"] == "all"
    assert plan_search("search firefox", all_on)["query"] == "firefox"
    assert plan_search("can you open firefox", all_on)["query"] == "firefox"
    assert plan_search("open my documents", all_on)["query"] == "documents"
    assert plan_search("what is 2+2", all_on)["query"] == "2+2"
    assert plan_search("show me the time", all_on)["query"] == "time"
    assert plan_search("workspace two", all_on)["query"] == "workspace two"
    assert plan_search("$ windows firefox", all_on)["query"] == "firefox"
    assert plan_search("# settings wifi", all_on)["query"] == "wifi"
    assert plan_search("tell me what time it is", all_on)["query"] == "what time it is"
    assert evaluate_arithmetic(plan_search("what is 2 plus 2", all_on)["query"]) == 4
    assert evaluate_arithmetic(plan_search("what is two plus two", all_on)["query"]) == 4
    assert time_query_kind(plan_search("tell me what time it is", all_on)["query"]) == "time"
    assert time_query_kind(plan_search("what's the time right now", all_on)["query"]) == "time"
    assert plan_search("what is the answer to 2+2", all_on)["query"] == "2+2"
    assert time_query_kind(plan_search("what's the day", all_on)["query"]) == "date"
    assert time_query_kind(plan_search("tell me the day", all_on)["query"]) == "date"
    assert plan_search("convert 10 km to mi", all_on)["query"] == "10 km to mi"
    assert plan_search("can you close firefox", all_on)["query"] == "close firefox"
    assert plan_search("switch to term", all_on)["query"] == "term"
    assert plan_search("$ switch to term", all_on)["query"] == "term"
    assert plan_search("@ open cats", all_on)["query"] == "open cats"
    assert plan_search("=open 2", all_on)["query"] == "open 2"
    assert "units" in plan_search("10 km to mi", all_on)["providers"]
    assert "places" in plan_search("documents", all_on)["providers"]
    assert "time" in plan_search("time", all_on)["providers"]
    assert "path" in plan_search("~/docs", all_on)["providers"]
    assert "path" in plan_search("/tmp", all_on)["providers"]
    apps_only = _flags(
        enable_prefix_modes=False,
        enable_url_open=False,
        enable_path_open=False,
        enable_places=False,
        enable_bookmarks=False,
        enable_calculator=False,
        enable_unit_convert=False,
        enable_color_hex=False,
        enable_time_date=False,
        enable_window_search=False,
        enable_system_actions=False,
        enable_settings_search=False,
        enable_recent_files=False,
        show_web_search=False,
    )
    assert plan_search("x", apps_only)["providers"] == ["apps"]
    assert "units" not in plan_search("10 km to mi", apps_only)["providers"]
    assert plan_search("~/docs", apps_only)["providers"] == ["apps"]
