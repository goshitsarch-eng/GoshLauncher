from __future__ import annotations

import signal

import pytest

from ulauncher.modes.launcher.windows import (
    WindowInfo,
    activate_window,
    application_bus_name,
    application_object_path,
    compositor_list_commands,
    compositor_window_argv,
    match_windows,
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
    window_class_text,
    window_close_title,
    window_matches,
    window_recency_value,
    window_result_id,
    window_workspace_label,
    windows_from_hypr_clients,
    windows_from_i3_tree,
    windows_from_introspect_payload,
    windows_from_kwin_dump,
    windows_from_lswt_csv,
    windows_from_niri_windows,
    windows_from_qtile_windows,
    windows_from_sway_tree,
    windows_from_wlrctl_list,
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


def test_window_class_text_and_workspace_label_match_goshos() -> None:
    assert window_class_text("Firefox", "Navigator", "org.mozilla.firefox") == "Firefox Navigator org.mozilla.firefox"
    assert window_workspace_label(0) == "Workspace 1"
    assert window_workspace_label(2) == "Workspace 3"
    assert window_workspace_label(-1) == "Switch to window"
    assert window_workspace_label(1, True) == "On all workspaces"
    unknown = WindowInfo(wid="0x1", title="Term", wm_class="foot", desktop=-1, sticky=False)
    assert window_matches(unknown, "") is True

    rows = match_windows("workspace 2", windows=[])
    assert rows
    assert rows[0]["icon"] == "view-app-grid-symbolic"
    nav = WindowInfo(
        wid="0x2",
        title="Mozilla Firefox",
        wm_class=window_class_text("Firefox", "Navigator", "org.mozilla.firefox"),
        desktop=0,
    )
    assert window_matches(nav, "nav")
    assert window_matches(nav, "firefox navigator")


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
    compositor = [WindowInfo(wid="hypr:0x1", title="Wayland", wm_class="app", desktop=0)]
    assert pick_window_list([], [], [], compositor) == compositor
    native_one = [WindowInfo(wid="0x1", title="X", wm_class="x", desktop=0)]
    compositor_two = [*compositor, WindowInfo(wid="hypr:0x2", title="Other", wm_class="b", desktop=0)]
    assert pick_window_list(native_one, [], [], compositor_two) == compositor_two


def test_hypr_sway_niri_window_payloads() -> None:
    hypr = windows_from_hypr_clients(
        [
            {
                "address": "0xabc",
                "title": "Firefox",
                "class": "firefox",
                "pid": 9,
                "workspace": {"id": 2},
                "focusHistoryID": 0,
                "mapped": True,
            },
            {"address": "0xhid", "title": "Hidden", "class": "x", "hidden": True},
            {"address": "", "title": "No id", "class": "x"},
        ]
    )
    assert len(hypr) == 1
    assert hypr[0].wid == "hypr:0xabc"
    assert hypr[0].desktop == 1
    assert hypr[0].app_id == "firefox"
    sway = windows_from_sway_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "3",
                    "nodes": [
                        {
                            "id": 42,
                            "type": "con",
                            "name": "Terminal",
                            "app_id": "foot",
                            "pid": 8,
                            "focused": True,
                        }
                    ],
                },
                {"type": "workspace", "name": "__i3_scratch", "nodes": [{"id": 1, "type": "con", "name": "scratch"}]},
            ],
        }
    )
    assert len(sway) == 1
    assert sway[0].wid == "sway:42"
    assert sway[0].desktop == 2
    assert sway[0].app_id == "foot"
    niri = windows_from_niri_windows(
        [
            {"id": 7, "title": "Notes", "app_id": "org.gnome.TextEditor", "workspace_id": 1, "is_focused": True},
            {"id": 8, "title": "", "app_id": ""},
        ]
    )
    assert len(niri) == 1
    assert niri[0].wid == "niri:7"
    assert niri[0].wm_class == "org.gnome.TextEditor"
    assert compositor_window_argv("hypr:0xabc", "focus") == [
        "hyprctl",
        "dispatch",
        "focuswindow",
        "address:0xabc",
    ]
    assert compositor_window_argv("sway:42", "close") == ["swaymsg", "[con_id=42]", "kill"]
    i3 = windows_from_i3_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "2",
                    "nodes": [
                        {
                            "id": 9,
                            "type": "con",
                            "name": "Firefox",
                            "window_properties": {"class": "firefox", "title": "Firefox"},
                            "pid": 4,
                            "focused": True,
                        }
                    ],
                }
            ],
        }
    )
    assert len(i3) == 1
    assert i3[0].wid == "i3:9"
    assert i3[0].wm_class == "firefox"
    assert i3[0].desktop == 1
    assert compositor_window_argv("i3:9", "focus") == ["i3-msg", "[con_id=9]", "focus"]
    assert compositor_window_argv("i3:9", "close") == ["i3-msg", "[con_id=9]", "kill"]
    assert compositor_window_argv("niri:7", "focus") == [
        "niri",
        "msg",
        "action",
        "focus-window",
        "--id",
        "7",
    ]
    assert compositor_window_argv("0x1", "focus") is None
    wlr = windows_from_wlrctl_list("firefox: Mozilla Firefox\nfoot: Terminal: bash\n: \n")
    assert [row.app_id for row in wlr] == ["firefox", "foot"]
    assert wlr[1].title == "Terminal: bash"
    assert compositor_window_argv(wlr[0].wid, "focus") == [
        "wlrctl",
        "toplevel",
        "focus",
        "app_id:firefox",
        "title:Mozilla Firefox",
    ]
    assert compositor_window_argv(wlr[0].wid, "close") is None
    hypr_alt = windows_from_hypr_clients(
        [
            {
                "address": "0xdef",
                "title": "Term",
                "class": "foot",
                "workspace": {"id": 1},
                "focusHistoryId": 3,
                "mapped": True,
            }
        ]
    )
    assert hypr_alt[0].wid == "hypr:0xdef"
    assert hypr_alt[0].user_time == 10**9 - 3
    niri_cmds = compositor_list_commands({"NIRI_SOCKET": "/run/niri.sock"})
    assert niri_cmds[0][0] == ["niri", "msg", "--json", "windows"]
    hypr_cmds = compositor_list_commands({"HYPRLAND_INSTANCE_SIGNATURE": "sig"})
    assert hypr_cmds[0][0] == ["hyprctl", "-j", "clients"]
    i3_cmds = compositor_list_commands({"I3SOCK": "/run/i3/ipc.sock"})
    assert i3_cmds[0][0] == ["i3-msg", "-t", "get_tree"]
    default_cmds = compositor_list_commands({})
    assert [argv for argv, _parser in default_cmds] == [
        ["hyprctl", "-j", "clients"],
        ["swaymsg", "-t", "get_tree"],
        ["niri", "msg", "--json", "windows"],
        ["i3-msg", "-t", "get_tree"],
    ]


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
    calls.clear()
    activate_window(
        {"kind": "focus", "wid": "hypr:0xabc", "app_id": "org.gnome.Console"},
        application_activate=lambda app: calls.append(("app", app)) or True,
    )
    assert calls == [("x11", "hypr:0xabc")]
    calls.clear()
    activate_window({"kind": "close", "wid": "niri:7", "pid": 9})
    assert calls == [("close", "niri:7")]
    calls.clear()
    wlr_wid = windows_from_wlrctl_list("firefox: Mozilla Firefox")[0].wid
    activate_window({"kind": "close", "wid": wlr_wid, "pid": 9})
    assert calls == [("close", wlr_wid), ("sig", 9, signal.SIGTERM)]
    calls.clear()
    activate_window(
        {"kind": "focus", "wid": wlr_wid, "app_id": "firefox"},
        application_activate=lambda app: calls.append(("app", app)) or True,
    )
    assert calls == [("x11", wlr_wid)]


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


def test_lswt_csv_lists_ext_foreign_toplevels() -> None:
    rows = windows_from_lswt_csv('Firefox,firefox,ext-1\n"Notes, 1",org.gnome.TextEditor,ext-2\n,,\n')
    assert [row.app_id for row in rows] == ["firefox", "org.gnome.TextEditor"]
    assert rows[1].title == "Notes, 1"
    assert rows[0].wid == "lswt:ext-1"
    assert compositor_window_argv(rows[0].wid, "focus") is None


def test_kwin_dump_lists_and_activates_plasma_windows() -> None:
    rows = windows_from_kwin_dump(
        '{"id":"{aaa}","title":"Firefox","app_id":"firefox"}\n'
        '{"id":"{bbb}","title":"","app_id":""}\n'
        '[{"id":"{ccc}","title":"Dolphin","resourceClass":"org.kde.dolphin"}]\n'
    )
    assert [row.wid for row in rows] == ["kwin:{aaa}"]
    assert rows[0].app_id == "firefox"
    array_rows = windows_from_kwin_dump([{"id": "{ccc}", "title": "Dolphin", "resourceClass": "org.kde.dolphin"}])
    assert array_rows[0].wid == "kwin:{ccc}"
    assert array_rows[0].app_id == "org.kde.dolphin"
    assert compositor_window_argv("kwin:{aaa}", "focus") == ["kdotool", "windowactivate", "{aaa}"]
    assert compositor_window_argv("kwin:{aaa}", "close") == ["kdotool", "windowclose", "{aaa}"]


def test_qtile_windows_list_and_activate() -> None:
    rows = windows_from_qtile_windows(
        [
            {"id": 12, "name": "Firefox", "wm_class": ["Navigator", "firefox"], "group": "2", "pid": 8},
            {"id": 0, "name": "scratch", "wm_class": "scratch"},
            {"name": "missing-id", "wm_class": "x"},
            {"id": 3, "name": "", "wm_class": []},
        ]
    )
    assert [row.wid for row in rows] == ["qtile:12", "qtile:0"]
    assert rows[0].wm_class == "firefox"
    assert rows[0].desktop == 1
    assert rows[0].pid == 8
    assert compositor_window_argv("qtile:12", "focus") == [
        "qtile",
        "cmd-obj",
        "-o",
        "window",
        "12",
        "-f",
        "focus",
    ]
    assert compositor_window_argv("qtile:12", "close") == [
        "qtile",
        "cmd-obj",
        "-o",
        "window",
        "12",
        "-f",
        "kill",
    ]
    wrapped = windows_from_qtile_windows({"windows": [{"id": 4, "title": "Foot", "wm_class": "foot"}]})
    assert wrapped[0].wid == "qtile:4"
    assert wrapped[0].title == "Foot"


def test_match_windows_reads_cached_snapshot() -> None:
    from ulauncher.modes.launcher.windows import invalidate_windows, match_windows, store_window_snapshot

    invalidate_windows()
    try:
        store_window_snapshot([WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox", desktop=0, pid=11)])
        rows = match_windows("fire", 6)
        assert rows[0]["title"] == "Mozilla Firefox"
        assert rows[0]["wid"] == "0x1"
    finally:
        invalidate_windows()


def test_windows_cache_ttl_and_freshness() -> None:
    from ulauncher.modes.launcher.windows import invalidate_windows, store_window_snapshot, windows_cache_is_fresh

    invalidate_windows()
    try:
        assert windows_cache_is_fresh() is False
        store_window_snapshot([], now=10.0)
        assert windows_cache_is_fresh(now=10.2) is True
        assert windows_cache_is_fresh(now=10.5) is False
    finally:
        invalidate_windows()


def test_ensure_windows_skips_on_ready_when_cache_is_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import (
        ensure_windows,
        invalidate_windows,
        store_window_snapshot,
        windows_cache_is_fresh,
    )

    invalidate_windows()
    idle: list[object] = []
    monkeypatch.setattr("ulauncher.utils.scheduling.run_when_idle", idle.append)
    try:
        store_window_snapshot([WindowInfo(wid="0x1", title="Term", wm_class="foot", desktop=0)])
        assert windows_cache_is_fresh()
        fired: list[int] = []
        ensure_windows(lambda: fired.append(1))
        assert fired == []
        assert idle == []
    finally:
        invalidate_windows()


def test_ensure_windows_schedules_refresh_when_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from ulauncher.modes.launcher.windows import (
        ensure_windows,
        invalidate_windows,
        store_window_snapshot,
        windows_cache_is_fresh,
    )

    invalidate_windows()
    idle: list[object] = []
    monkeypatch.setattr(
        "ulauncher.utils.scheduling.run_when_idle",
        lambda fn: idle.append(fn) or SimpleNamespace(cancel=lambda: None),
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.list_windows",
        lambda: store_window_snapshot([WindowInfo(wid="0x2", title="Code", wm_class="code", desktop=0)]),
    )
    try:
        fired: list[int] = []
        ensure_windows(lambda: fired.append(1))
        assert fired == []
        assert windows_cache_is_fresh() is False
        assert idle
        idle[0]()  # type: ignore[operator]
        assert fired == [1]
        assert windows_cache_is_fresh()
    finally:
        invalidate_windows()
