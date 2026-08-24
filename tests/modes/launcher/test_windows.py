from __future__ import annotations

from ulauncher.modes.launcher.windows import parse_window_intent, parse_workspace_query


def test_workspace_query_needs_the_word() -> None:
    assert parse_workspace_query("2") is None
    assert parse_workspace_query("workspace 2") == 1
    assert parse_workspace_query("go to workspace 3") == 2
    assert parse_workspace_query("switch to workspace two") == 1


def test_close_and_kill_intents() -> None:
    assert parse_window_intent("close firefox") == ("close", "firefox")
    assert parse_window_intent("close the firefox window") == ("close", "firefox")
    assert parse_window_intent("kill firefox") == ("kill", "firefox")
    assert parse_window_intent("force quit firefox") == ("kill", "firefox")
    assert parse_window_intent("quit firefox") == ("quit", "firefox")
    assert parse_window_intent("firefox") == ("focus", "firefox")
