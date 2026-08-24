from __future__ import annotations

import signal

import pytest

from ulauncher.modes.launcher.windows import (
    WindowInfo,
    activate_window,
    application_bus_name,
    application_object_path,
    parse_window_close_query,
    parse_window_intent,
    parse_workspace_query,
    parse_workspace_switch_query,
    pick_window_list,
    should_force_quit_window,
    sort_windows_most_recent,
    switch_workspace,
    tab_ranks_from_introspect_payload,
    take_window_results,
    window_close_title,
    window_matches,
    window_recency_value,
    window_result_id,
    windows_from_introspect_payload,
    workspace_index_in_range,
    workspace_label_matches,
    workspace_result_id,
    workspace_switch_steps,
    workspace_switch_title,
)


def test_workspace_query_needs_the_word() -> None:
    assert parse_workspace_query("2") is None
    assert parse_workspace_query("workspace 2") == 1
    assert parse_workspace_query("go to workspace 3") == 2
    assert parse_workspace_query("switch to workspace two") == 1
    parsed = parse_workspace_switch_query("workspace twenty")
    assert parsed is not None
    assert parsed["number"] == 20
    twenty_one = parse_workspace_switch_query("switch to workspace twenty-one")
    assert twenty_one is not None
    assert twenty_one["number"] == 21
    hundred = parse_workspace_switch_query("workspace one hundred twenty")
    assert hundred is not None
    assert hundred["number"] == 120
    assert parse_workspace_switch_query("ws 1") == {"index": 0, "number": 1}
    assert parse_workspace_switch_query("workspace") is None
    assert workspace_index_in_range(1, 3) is True
    assert workspace_index_in_range(3, 3) is False


def test_close_and_kill_intents() -> None:
    assert parse_window_intent("close firefox") == ("close", "firefox")
    assert parse_window_intent("close the firefox window") == ("close", "firefox")
    assert parse_window_intent("kill firefox") == ("kill", "firefox")
    assert parse_window_intent("force quit firefox") == ("kill", "firefox")
    assert parse_window_intent("quit firefox") == ("quit", "firefox")
    assert parse_window_intent("firefox") == ("focus", "firefox")
    close = parse_window_close_query("close the firefox")
    assert close is not None
    assert close["title"] == "firefox"
    assert parse_window_close_query("close my terminal")["title"] == "terminal"
    assert parse_window_close_query("close the firefox application")["title"] == "firefox"
    assert parse_window_close_query("kill firefox windows")["title"] == "firefox"
    assert parse_window_close_query("KILL Chrome")["intent"] == "kill"
    assert parse_window_close_query("force-quit firefox")["intent"] == "kill"
    assert parse_window_close_query("force close firefox")["intent"] == "kill"
    assert parse_window_close_query("close") is None
    assert parse_window_close_query("firefox") is None
    assert should_force_quit_window("kill") is True
    assert should_force_quit_window("close") is False
    assert should_force_quit_window("quit") is False


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
    editor = WindowInfo(wid="0x4", title="Notes", wm_class="org.gnome.TextEditor", desktop=0)
    assert window_matches(editor, "texted")
    assert not window_matches(editor, "org")
    assert not window_matches(editor, "ome")
    firefox = WindowInfo(wid="0x5", title="Firefox", wm_class="Navigator", desktop=1)
    assert window_matches(firefox, "2")
    assert not window_matches(firefox, "workspace")
    assert not window_matches(firefox, "spa")
    assert not window_matches(firefox, "work")
    assert not window_matches(firefox, "o")
    assert window_matches(firefox, "firefox navigator")
    assert not window_matches(firefox, "firefox chrome")


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


def test_window_and_workspace_result_ids() -> None:
    assert workspace_result_id(2) == "workspace:2"
    assert window_result_id("0x42", "Firefox", "Navigator", "Workspace 1") == "0x42"
    assert window_result_id("", "Firefox", "Navigator", "Workspace 1") == "Firefox\0Navigator\0Workspace 1"


def test_introspect_payload_lists_wayland_windows() -> None:
    payload = {
        0x1A00001: {"title": "Firefox", "wm-class": "firefox", "pid": 42},
        2: {"title": "Hidden", "wm-class": "x", "is-hidden": True},
        3: {"title": "", "wm-class": ""},
        4: {"title": "Term", "app-id": "org.gnome.Console"},
    }
    rows = windows_from_introspect_payload(payload)
    assert [row.title for row in rows] == ["Firefox", "Term"]
    assert rows[0].wid == hex(0x1A00001)
    assert rows[0].wm_class == "firefox"
    assert rows[0].pid == 42
    assert rows[0].app_id == ""
    assert rows[1].wm_class == "org.gnome.Console"
    assert rows[1].app_id == "org.gnome.Console"
    ranks = tab_ranks_from_introspect_payload(payload)
    assert ranks["firefox"] == 0
    native = [WindowInfo(wid="0x1", title="Only X11", wm_class="x", desktop=0)]
    wayland = windows_from_introspect_payload(payload)
    picked = pick_window_list(native, [], wayland)
    assert picked == wayland
    assert pick_window_list(native, [], []) == native
    assert pick_window_list([], [], []) == []


def test_application_bus_name_strips_desktop_suffix() -> None:
    assert application_bus_name("org.gnome.Console.desktop") == "org.gnome.Console"
    assert application_bus_name("org.gnome.Console") == "org.gnome.Console"
    assert application_bus_name("") == ""
    assert application_object_path("org.gnome.Console") == "/org/gnome/Console"
    assert application_object_path("") == ""


def test_activate_window_uses_application_activate_on_wayland(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("ulauncher.modes.launcher.windows.session_has_x11_window_control", lambda: False)
    monkeypatch.setattr("ulauncher.modes.launcher.windows._focus_window", lambda wid: calls.append(("x11", wid)))
    monkeypatch.setattr("ulauncher.modes.launcher.windows._close_window", lambda wid: calls.append(("close", wid)))
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._signal_pid", lambda pid, sig: calls.append(("sig", pid, sig))
    )
    activate_window(
        {"kind": "focus", "wid": "0x1", "app_id": "org.gnome.Console"},
        application_activate=lambda app: calls.append(("app", app)) or True,
    )
    assert calls == [("x11", "0x1"), ("app", "org.gnome.Console")]
    calls.clear()
    monkeypatch.setattr("ulauncher.modes.launcher.windows.session_has_x11_window_control", lambda: True)
    activate_window(
        {"kind": "focus", "wid": "0x1", "app_id": "org.gnome.Console"},
        application_activate=lambda app: calls.append(("app", app)) or True,
    )
    assert calls == [("x11", "0x1")]
    calls.clear()
    monkeypatch.setattr("ulauncher.modes.launcher.windows.session_has_x11_window_control", lambda: False)
    activate_window({"kind": "close", "wid": "0x1", "pid": 9})
    assert calls == [("close", "0x1"), ("sig", 9, signal.SIGTERM)]
    calls.clear()
    activate_window({"kind": "kill", "pid": 9})
    assert calls == [("sig", 9, signal.SIGKILL)]


def test_wayland_workspace_switch_prefers_compositor_ipc() -> None:
    ran: list[list[str]] = []

    def run(argv: list[str]) -> bool:
        ran.append(argv)
        return True

    used = switch_workspace(
        2,
        x11=False,
        which=lambda name: name if name == "hyprctl" else None,
        run=run,
        kwin=lambda _desktop: False,
        ewmh=lambda _index: False,
    )
    assert used == "hyprctl"
    assert ran == [["hyprctl", "dispatch", "workspace", "3"]]
    steps = workspace_switch_steps(2, x11=False)
    assert steps[0]["kind"] == "kwin"
    assert steps[0]["desktop"] == 3


def test_x11_workspace_switch_uses_wmctrl_before_kwin() -> None:
    ran: list[list[str]] = []

    def run(argv: list[str]) -> bool:
        ran.append(argv)
        return True

    used = switch_workspace(
        1,
        x11=True,
        which=lambda name: name if name == "wmctrl" else None,
        run=run,
        kwin=lambda _desktop: True,
        ewmh=lambda _index: False,
    )
    assert used == "wmctrl"
    assert ran == [["wmctrl", "-s", "1"]]


def test_x11_workspace_switch_falls_back_to_ewmh() -> None:
    desktops: list[int] = []
    used = switch_workspace(
        0,
        x11=True,
        which=lambda _name: None,
        run=lambda _argv: False,
        kwin=lambda _desktop: False,
        ewmh=lambda index: desktops.append(index) or True,
    )
    assert used == "ewmh"
    assert desktops == [0]
