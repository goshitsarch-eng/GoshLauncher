from __future__ import annotations

from ulauncher.modes.launcher.windows import (
    WindowInfo,
    parse_window_intent,
    parse_workspace_query,
    sort_windows_most_recent,
    take_window_results,
    window_close_title,
    window_matches,
    window_recency_value,
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
    assert window_matches(win, "") is True
    assert window_matches(
        WindowInfo(wid="0x2", title="Mozilla Firefox", wm_class="Navigator.firefox", desktop=0),
        "mozilla firefox",
    )
    assert not window_matches(
        WindowInfo(wid="0x3", title="Mozilla Firefox", wm_class="Navigator.firefox", desktop=0),
        "mozilla terminal",
    )


def test_take_window_results_workspace_consumes_a_slot() -> None:
    switch = {"kind": "workspace", "title": "Switch to Workspace 2"}
    windows = [{"kind": "focus", "title": "Firefox"}, {"kind": "focus", "title": "Terminal"}]
    taken = take_window_results(switch, windows, 1)
    assert taken == [switch]
    taken = take_window_results(switch, windows, 2)
    assert [row["title"] for row in taken] == ["Switch to Workspace 2", "Firefox"]


def test_window_recency_prefers_front_tab_then_user_time() -> None:
    assert window_recency_value(0, 3, 10) > window_recency_value(1, 3, 999999)
    older = WindowInfo(wid="1", title="Old", wm_class="old", desktop=0, user_time=50)
    newer = WindowInfo(wid="2", title="New", wm_class="new", desktop=0, user_time=5)
    # stacking/tab order: newer is index 0
    ordered = sort_windows_most_recent([newer, older])
    assert [win.title for win in ordered] == ["New", "Old"]
