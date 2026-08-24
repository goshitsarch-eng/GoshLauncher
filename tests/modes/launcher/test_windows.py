from __future__ import annotations

from ulauncher.modes.launcher.windows import (
    WindowInfo,
    parse_window_intent,
    parse_workspace_query,
    window_close_title,
    window_matches,
    workspace_label_matches,
    workspace_switch_title,
)


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


def test_workspace_switch_title_matches_goshos() -> None:
    assert workspace_switch_title(2) == "Switch to Workspace 2"
    assert window_close_title("kill", "Firefox") == "Kill Firefox"
    assert window_close_title("close", "Firefox") == "Close Firefox"


def test_workspace_label_matches_number_and_sticky() -> None:
    assert workspace_label_matches("Workspace 2", "2")
    assert workspace_label_matches("Workspace 2", "workspace two")
    assert workspace_label_matches("Workspace 2", "ws 2")
    assert not workspace_label_matches("Workspace 2", "workspace")
    assert workspace_label_matches("On all workspaces", "sticky")
    assert workspace_label_matches("On all workspaces", "on all")
    win = WindowInfo(wid="0x1", title="Firefox", wm_class="firefox", desktop=1, pid=1, sticky=False)
    assert window_matches(win, "2")
    assert not window_matches(win, "workspace")
