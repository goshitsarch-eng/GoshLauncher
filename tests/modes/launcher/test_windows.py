from __future__ import annotations

import signal

import pytest

from ulauncher.modes.launcher.windows import (
    KWIN_LIST_SCRIPT,
    WindowInfo,
    activate_window,
    application_bus_name,
    application_object_path,
    bus_pid_for_window,
    compositor_list_commands,
    compositor_window_argv,
    ewmh_window_type,
    filter_listed_windows,
    gtk_unique_props_from_mapping,
    gtk_unique_props_from_xprop,
    hypr_current_desktop,
    hypr_workspace_count,
    i3ipc_current_desktop,
    i3ipc_workspace_count,
    is_unique_gtk_window,
    listed_current_desktop,
    listed_workspace_count,
    match_windows,
    merge_window_lists,
    niri_current_desktop,
    niri_focus_user_time,
    niri_workspace_count,
    overlay_window_info,
    parse_window_close_query,
    parse_window_intent,
    parse_wmctrl_current_desktop,
    parse_wmctrl_desktops,
    parse_wmctrl_lx,
    parse_workspace_query,
    parse_workspace_switch_query,
    parse_xprop_window,
    pick_window_list,
    qtile_current_desktop,
    qtile_workspace_count,
    should_force_quit_window,
    should_list_window,
    sort_windows_most_recent,
    switch_workspace,
    tab_ranks_from_introspect_payload,
    take_window_results,
    window_class_text,
    window_close_title,
    window_inspect_from_xprop,
    window_is_searchable,
    window_matches,
    window_recency_value,
    window_result_id,
    window_workspace_label,
    windows_from_ext_foreign_handles,
    windows_from_hypr_clients,
    windows_from_i3_tree,
    windows_from_introspect_payload,
    windows_from_kwin_dump,
    windows_from_lswt_csv,
    windows_from_niri_windows,
    windows_from_qtile_windows,
    windows_from_sway_tree,
    windows_from_wlrctl_list,
    workspace_desktop_from_name,
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
    desktops = "0  * DG: 1920x1080  VP: 0,0  WA: 0,0 1920x1080  1\n1  - DG: 1920x1080  VP: 0,0  WA: 0,0 1920x1080  2\n"
    assert parse_wmctrl_desktops(desktops) == 2
    assert parse_wmctrl_current_desktop(desktops) == 0
    assert (
        parse_wmctrl_current_desktop("0  - DG: 1x1  VP: 0,0  WA: 0,0 1x1  1\n1  * DG: 1x1  VP: 0,0  WA: 0,0 1x1  2\n")
        == 1
    )
    assert parse_wmctrl_desktops("") is None
    assert parse_wmctrl_desktops("Cannot get client list properties.\n") is None
    assert parse_wmctrl_current_desktop("Cannot get client list properties.\n") is None


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
    assert match_windows("workspace 99", windows=[], workspace_count=3) == []
    in_range = match_windows("workspace 2", windows=[], workspace_count=3)
    assert in_range[0]["kind"] == "workspace"
    assert in_range[0]["id"] == "workspace:2"
    unknown = match_windows("workspace 99", windows=[])
    assert unknown[0]["kind"] == "workspace"
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


def test_should_list_window_matches_goshos() -> None:
    listed = ["normal", "dialog"]
    assert should_list_window({}, False, "normal", listed) is True
    assert should_list_window(None, False, "normal", listed) is False
    assert should_list_window({}, True, "normal", listed) is False
    assert should_list_window({}, False, "dock", listed) is False
    assert ewmh_window_type([]) == "normal"
    assert ewmh_window_type(["_NET_WM_WINDOW_TYPE_DIALOG"]) == "dialog"
    assert ewmh_window_type(["_NET_WM_WINDOW_TYPE_DOCK"]) == "dock"
    assert should_list_window(True, False, ewmh_window_type([])) is True
    assert should_list_window(True, True, "normal") is False
    assert should_list_window(True, False, ewmh_window_type(["_NET_WM_WINDOW_TYPE_DOCK"])) is False


def test_window_title_still_matches_workspace_spa_work() -> None:
    # goshos only keeps those needles off the shared Workspace N label
    named = WindowInfo(wid="0x7", title="Workspace Settings", wm_class="gnome-control-center", desktop=0)
    assert window_matches(named, "workspace")
    assert window_matches(WindowInfo(wid="0x8", title="Spark", wm_class="spark", desktop=0), "spa")
    assert window_matches(WindowInfo(wid="0x9", title="Work", wm_class="work", desktop=0), "work")
    sticky = WindowInfo(wid="0x6", title="Notes", wm_class="gedit", desktop=0, sticky=True)
    assert window_matches(sticky, "all workspaces")
    firefox = WindowInfo(wid="0x5", title="Firefox", wm_class="Navigator", desktop=1)
    assert not window_matches(firefox, "workspace")
    assert not window_matches(firefox, "spa")
    assert not window_matches(firefox, "work")


def test_take_window_results_workspace_consumes_a_slot() -> None:
    switch = {"kind": "workspace", "title": "Switch to Workspace 2"}
    windows = [{"kind": "focus", "title": "Firefox"}, {"kind": "focus", "title": "Terminal"}]
    taken = take_window_results(switch, windows, 1)
    assert taken == [switch]
    taken = take_window_results(switch, windows, 2)
    assert [row["title"] for row in taken] == ["Switch to Workspace 2", "Firefox"]
    assert take_window_results(switch, windows, 0) == []


def test_window_recency_prefers_front_tab_then_user_time() -> None:
    assert window_recency_value(0, 3, 10) > window_recency_value(1, 3, 999999)
    assert window_recency_value(-1, 3, 50) == 50
    older = WindowInfo(wid="1", title="Old", wm_class="old", desktop=0, user_time=50)
    newer = WindowInfo(wid="2", title="New", wm_class="new", desktop=0, user_time=5)
    # compositor list order is stacking not focus — goshos sorts by user_time
    ordered = sort_windows_most_recent([newer, older])
    assert [win.title for win in ordered] == ["Old", "New"]
    tabbed = sort_windows_most_recent([older, newer], tab_ranks={"new": 0, "old": 1})
    assert [win.title for win in tabbed] == ["New", "Old"]
    twins = [
        WindowInfo(wid="0x1", title="A", wm_class="firefox", desktop=0),
        WindowInfo(wid="0x2", title="B", wm_class="firefox", desktop=0),
    ]
    # two windows share a class; alt-tab rank is per window id like goshos MetaWindow keys
    assert [win.title for win in sort_windows_most_recent(twins, tab_ranks={"0x1": 1, "0x2": 0, "firefox": 1})] == [
        "B",
        "A",
    ]
    assert window_recency_value(0, 3, 0) > window_recency_value(-1, 0, 999)
    titled = [
        WindowInfo(wid="a", title="Firefox", wm_class="x", desktop=0, user_time=1),
        WindowInfo(wid="b", title="Term", wm_class="y", desktop=0, user_time=9),
    ]
    assert [win.title for win in sort_windows_most_recent(titled, tab_ranks={"firefox": 0})] == ["Firefox", "Term"]


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
    focused = tab_ranks_from_introspect_payload(
        {
            1: {"title": "Back", "wm-class": "old"},
            2: {"title": "Front", "wm-class": "new", "has-focus": True},
        }
    )
    assert focused["new"] == 0
    assert focused["old"] == 1
    focused_rows = windows_from_introspect_payload(
        {
            1: {"title": "Back", "wm-class": "old"},
            2: {"title": "Front", "wm-class": "new", "has-focus": True},
        }
    )
    by_focus = {row.title: row for row in focused_rows}
    assert by_focus["Front"].user_time == 1
    assert by_focus["Back"].user_time == 0
    sandboxed = windows_from_introspect_payload(
        {
            5: {
                "title": "Mozilla Firefox",
                "wm-class": "firefox",
                "sandboxed-app-id": "org.mozilla.firefox",
                "app-id": "firefox.desktop",
            }
        }
    )
    assert sandboxed[0].wm_class == "firefox org.mozilla.firefox"
    assert sandboxed[0].app_id == "firefox.desktop"
    assert window_matches(sandboxed[0], "mozilla")


def test_pick_window_list_merges_native_skip_taskbar_onto_compositor() -> None:
    native = [WindowInfo(wid="0x1", title="Only X11", wm_class="x", desktop=0)]
    wayland = [
        WindowInfo(wid="0x1a00001", title="Firefox", wm_class="firefox", desktop=0),
        WindowInfo(wid="0x2", title="Term", wm_class="org.gnome.Console", desktop=0, app_id="org.gnome.Console"),
    ]
    assert [row.title for row in pick_window_list(native, [], wayland)] == ["Only X11", "Firefox", "Term"]
    assert pick_window_list(native, [], []) == native
    assert pick_window_list([], [], []) == []
    compositor = [WindowInfo(wid="hypr:0x1", title="Wayland", wm_class="app", desktop=0)]
    assert pick_window_list([], [], [], compositor) == compositor
    native_one = [WindowInfo(wid="0x1", title="X", wm_class="x", desktop=0)]
    compositor_two = [*compositor, WindowInfo(wid="hypr:0x2", title="Other", wm_class="b", desktop=0)]
    assert [row.title for row in pick_window_list(native_one, [], [], compositor_two)] == ["X", "Wayland", "Other"]
    ewmh = [
        WindowInfo(
            wid="0xabc",
            title="Mozilla Firefox",
            wm_class="firefox",
            desktop=2,
            pid=42,
            skip_taskbar=False,
            user_time=99,
            gtk_unique_bus_name=":1.9",
            gtk_application_object_path="/org/mozilla/Firefox",
            gtk_app_id="firefox",
        )
    ]
    ext = [WindowInfo(wid="ext:ident", title="Mozilla Firefox", wm_class="firefox", desktop=0, pid=0, app_id="firefox")]
    merged = pick_window_list(ewmh, [], [], ext)
    assert len(merged) == 1
    row = merged[0]
    assert row.wid == "0xabc"
    assert row.desktop == 2
    assert row.pid == 42
    assert row.user_time == 99
    assert row.gtk_unique_bus_name == ":1.9"
    dock_native = [
        WindowInfo(wid="0x2", title="Dash", wm_class="dash-to-dock", desktop=0, skip_taskbar=True, window_type="dock")
    ]
    dock_ext = [WindowInfo(wid="ext:dash", title="Dash", wm_class="dash-to-dock", desktop=0, app_id="dash-to-dock")]
    dock = overlay_window_info(dock_ext[0], dock_native[0])
    assert dock.skip_taskbar is True
    assert dock.window_type == "dock"
    assert window_is_searchable(dock) is False
    twins_native = [
        WindowInfo(wid="0x10", title="Terminal", wm_class="kgx", desktop=1, pid=8),
        WindowInfo(wid="0x11", title="Terminal", wm_class="org.gnome.Console", desktop=3, pid=9),
    ]
    twins_ext = [
        WindowInfo(wid="ext:a", title="Terminal", wm_class="kgx", desktop=0, app_id="kgx"),
        WindowInfo(wid="ext:b", title="Terminal", wm_class="org.gnome.Console", desktop=0, app_id="org.gnome.Console"),
    ]
    paired = merge_window_lists(twins_native, twins_ext)
    assert [row.wid for row in paired] == ["0x10", "0x11"]
    assert [row.desktop for row in paired] == [1, 3]
    assert [row.app_id for row in paired] == ["kgx", "org.gnome.Console"]


def test_introspect_payload_honors_skip_taskbar_and_type() -> None:
    payload = {
        1: {"title": "Firefox", "wm-class": "firefox"},
        2: {"title": "Panel", "wm-class": "gnome-shell", "is-skip-taskbar": True},
        3: {"title": "Dock", "wm-class": "dock", "window-type": "dock"},
        4: {"title": "Dialog", "wm-class": "app", "window-type": "dialog"},
        5: {"title": "Closed", "wm-class": "x", "workspace": None},
        6: {"title": "Stand-in", "wm-class": "y", "workspace": {}},
        7: {"title": "First ws", "wm-class": "z", "workspace": 0},
        8: {"title": "Enum", "wm-class": "e", "window-type": 2},
        9: {"title": "Second ws", "wm-class": "w", "workspace": 1},
    }
    assert [row.title for row in windows_from_introspect_payload(payload)] == [
        "Firefox",
        "Panel",
        "Dock",
        "Dialog",
        "Stand-in",
        "First ws",
        "Enum",
        "Second ws",
    ]
    by_title = {row.title: row for row in windows_from_introspect_payload(payload)}
    assert by_title["Panel"].skip_taskbar is True
    assert by_title["Dock"].window_type == "dock"
    assert window_is_searchable(by_title["Firefox"])
    assert not window_is_searchable(by_title["Panel"])
    assert not window_is_searchable(by_title["Dock"])
    assert by_title["First ws"].desktop == 0
    assert by_title["Second ws"].desktop == 1
    assert window_matches(by_title["Second ws"], "workspace 2")
    assert by_title["Firefox"].sticky is False
    sticky = windows_from_introspect_payload({9: {"title": "Notes", "wm-class": "gedit", "on-all-workspaces": True}})
    assert sticky[0].sticky is True
    assert window_matches(sticky[0], "sticky")


def test_unique_gtk_window_needs_bus_path_and_app_id() -> None:
    unique = WindowInfo(
        wid="0x1",
        title="Settings",
        wm_class="org.gnome.Settings",
        desktop=0,
        gtk_app_id="org.gnome.Settings",
        gtk_unique_bus_name=":1.42",
        gtk_application_object_path="/org/gnome/Settings",
    )
    assert is_unique_gtk_window(unique) is True
    missing_id = WindowInfo(
        wid="0x2",
        title="Legacy",
        wm_class="app",
        desktop=0,
        gtk_unique_bus_name=":1.1",
        gtk_application_object_path="/org/app",
    )
    assert is_unique_gtk_window(missing_id) is False
    wayland_only = WindowInfo(
        wid="0x3",
        title="Term",
        wm_class="org.gnome.Console",
        desktop=0,
        app_id="org.gnome.Console",
    )
    assert is_unique_gtk_window(wayland_only) is False
    gtk_app_id, gtk_bus, gtk_path = gtk_unique_props_from_mapping(
        {
            "gtk-app-id": "org.gnome.Settings",
            "gtk-unique-bus-name": ":1.42",
            "gtk-application-object-path": "/org/gnome/Settings",
        }
    )
    assert (gtk_app_id, gtk_bus, gtk_path) == ("org.gnome.Settings", ":1.42", "/org/gnome/Settings")
    payload = {
        9: {
            "title": "Settings",
            "wm-class": "org.gnome.Settings",
            "gtk-app-id": "org.gnome.Settings",
            "gtk-unique-bus-name": ":1.42",
            "gtk-application-object-path": "/org/gnome/Settings",
        }
    }
    rows = windows_from_introspect_payload(payload)
    assert len(rows) == 1
    assert is_unique_gtk_window(rows[0]) is True


def test_wmctrl_list_drops_skip_taskbar_when_inspect_knows() -> None:
    text = (
        "0x01a00001  0 firefox.Firefox host Mozilla Firefox\n"
        "0x01a00002  0 panel.Panel host Top Bar\n"
        "0x01a00003  0 dock.Dock host Dock\n"
        "incomplete line\n"
    )
    rows = parse_wmctrl_lx(text)
    assert [row.title for row in rows] == ["Mozilla Firefox", "Top Bar", "Dock"]

    def inspect(wid: str) -> tuple[bool | None, str | None] | None:
        if wid == "0x01a00002":
            return True, "normal"
        if wid == "0x01a00003":
            return False, "dock"
        if wid == "0x01a00001":
            return False, "normal"
        return None

    kept = filter_listed_windows(rows, inspect)
    assert [row.title for row in kept] == ["Mozilla Firefox", "Top Bar", "Dock"]
    assert kept[0].skip_taskbar is False
    assert kept[1].skip_taskbar is True
    assert kept[2].window_type == "dock"
    assert not window_is_searchable(kept[1])
    assert not window_is_searchable(kept[2])
    assert filter_listed_windows(rows, None) == rows
    unknown = filter_listed_windows(rows, lambda _wid: None)
    assert [row.title for row in unknown] == ["Mozilla Firefox", "Top Bar", "Dock"]

    def inspect_gtk(wid: str) -> tuple[bool | None, str | None, str, str, str] | None:
        if wid == "0x01a00001":
            return False, "normal", "org.mozilla.firefox", ":1.9", "/org/mozilla/Firefox"
        if wid == "0x01a00002":
            return True, "normal", "", "", ""
        if wid == "0x01a00003":
            return False, "dock", "", "", ""
        return None

    enriched = filter_listed_windows(rows, inspect_gtk)
    assert [row.title for row in enriched] == ["Mozilla Firefox", "Top Bar", "Dock"]
    assert enriched[0].gtk_app_id == "org.mozilla.firefox"
    assert enriched[0].gtk_unique_bus_name == ":1.9"
    assert "org.mozilla.firefox" in enriched[0].wm_class
    assert is_unique_gtk_window(enriched[0]) is True
    assert enriched[1].skip_taskbar is True
    assert not window_is_searchable(enriched[1])
    assert enriched[2].window_type == "dock"
    assert not window_is_searchable(enriched[2])


def test_xprop_window_parse_skip_taskbar_and_gtk_unique() -> None:
    skip = window_inspect_from_xprop(
        "_NET_WM_STATE(ATOM) = _NET_WM_STATE_SKIP_TASKBAR, _NET_WM_STATE_SKIP_PAGER\n"
        "_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_DOCK\n"
    )
    assert skip is not None
    assert skip[0] is True
    assert skip[1] == "dock"
    missing = window_inspect_from_xprop("_NET_WM_STATE:  not found.\n_NET_WM_WINDOW_TYPE:  not found.\n")
    assert missing is None
    gtk = (
        '_GTK_APPLICATION_ID(UTF8_STRING) = "org.gnome.Settings"\n'
        '_GTK_UNIQUE_BUS_NAME(UTF8_STRING) = ":1.42"\n'
        '_GTK_APPLICATION_OBJECT_PATH(UTF8_STRING) = "/org/gnome/Settings"\n'
        "_NET_WM_STATE(ATOM) = \n"
        "_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_NORMAL\n"
    )
    flags = window_inspect_from_xprop(gtk)
    assert flags is not None
    assert flags[0] is False
    assert flags[1] == "normal"
    assert flags[2:] == ("org.gnome.Settings", ":1.42", "/org/gnome/Settings")
    assert gtk_unique_props_from_xprop(gtk) == ("org.gnome.Settings", ":1.42", "/org/gnome/Settings")
    assert parse_xprop_window(gtk)["_GTK_APPLICATION_ID"] == '"org.gnome.Settings"'


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
    assert [row.title for row in hypr] == ["Firefox", "Hidden"]
    assert hypr[0].wid == "hypr:0xabc"
    assert hypr[0].desktop == 1
    assert hypr[0].app_id == "firefox"
    special = windows_from_hypr_clients(
        [
            {
                "address": "0xsp",
                "title": "Scratch",
                "class": "foot",
                "workspace": {"id": -98},
                "mapped": True,
            }
        ]
    )
    assert special[0].desktop == -1
    assert window_workspace_label(special[0].desktop) == "Switch to window"
    assert not window_matches(special[0], "1")
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
    assert niri[0].user_time == 1
    niri_stamps = windows_from_niri_windows(
        [
            {"id": 1, "title": "Old", "app_id": "a", "focus_timestamp": {"secs": 1, "nanos": 0}},
            {"id": 2, "title": "New", "app_id": "b", "focus_timestamp": {"secs": 3, "nanos": 0}},
        ]
    )
    assert sort_windows_most_recent(niri_stamps)[0].title == "New"
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


def test_activate_window_skips_app_activate_when_atspi_grabs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("ulauncher.modes.launcher.windows.session_has_x11_window_control", lambda: False)
    monkeypatch.setattr("ulauncher.modes.launcher.windows._focus_window", lambda wid: calls.append(("x11", wid)))
    monkeypatch.setattr("ulauncher.modes.launcher.windows._grab_atspi_window", lambda _payload: True)
    activate_window(
        {"kind": "focus", "wid": "ext:ident", "app_id": "firefox", "title": "Mozilla Firefox"},
        application_activate=lambda app: calls.append(("app", app)) or True,
    )
    assert calls == [("x11", "ext:ident")]


def test_kill_uses_session_bus_pid_when_ext_foreign_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def probe(name: str) -> int | None:
        if name == "firefox":
            return 88
        if name == ":1.9":
            return 7
        return None

    assert bus_pid_for_window({"app_id": "firefox.desktop"}, probe=probe) == 88
    assert bus_pid_for_window({"gtk_unique_bus_name": ":1.9", "app_id": "x"}, probe=probe) == 7
    assert bus_pid_for_window({"app_id": "missing"}, probe=probe) == 0
    calls: list[tuple[object, ...]] = []

    def pid_from_payload(payload: object, probe: object = None) -> int:
        del probe
        data = payload if isinstance(payload, dict) else {}
        return 42 if str(data.get("app_id")) == "firefox" else 0

    monkeypatch.setattr("ulauncher.modes.launcher.windows.bus_pid_for_window", pid_from_payload)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._signal_pid",
        lambda pid, sig: calls.append(("sig", pid, sig)),
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._close_window", lambda wid: calls.append(("close", wid)))
    monkeypatch.setattr("ulauncher.modes.launcher.windows.session_has_x11_window_control", lambda: False)
    activate_window({"kind": "kill", "wid": "ext:abc", "pid": 0, "app_id": "firefox"})
    assert calls == [("sig", 42, signal.SIGKILL)]
    calls.clear()
    activate_window({"kind": "close", "wid": "ext:abc", "pid": 0, "app_id": "firefox"})
    assert calls == [("close", "ext:abc")]


def test_listed_workspace_count_prefers_ext_then_wmctrl(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr(
        "ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces",
        lambda: [{"removed": False}, {"removed": True}, {"name": "3"}],
    )
    assert listed_workspace_count() == 2
    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.shutil.which",
        lambda name: "wmctrl" if name == "wmctrl" else None,
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._text_command",
        lambda _argv: "0  * DG: 1x1  VP: 0,0  WA: 0,0 1x1  1\n1  - DG: 1x1  VP: 0,0  WA: 0,0 1x1  2\n",
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_desktop_count", lambda: 9)
    assert listed_workspace_count() == 2
    invalidate_workspace_count()


def test_compositor_workspace_count_uses_max_index() -> None:
    assert niri_workspace_count([{"id": 8, "idx": 1}, {"id": 9, "idx": 2}]) == 2
    assert niri_workspace_count([]) is None
    assert i3ipc_workspace_count([{"name": "1", "num": 1}, {"name": "5", "num": 5}]) == 5
    assert i3ipc_workspace_count([{"name": "2:www", "num": 2}, {"name": "code"}]) == 2
    assert i3ipc_workspace_count([{"name": "code"}, {"name": "__i3_scratch"}]) is None
    assert hypr_workspace_count([{"id": 1}, {"id": 3}, {"id": -98, "name": "special"}]) == 3
    assert hypr_workspace_count([{"id": -98}]) is None
    assert qtile_workspace_count({"1": {"name": "1"}, "5": {"name": "5"}}) == 5
    assert qtile_workspace_count({"code": {"name": "code"}}) is None
    assert qtile_workspace_count([{"name": "2"}, {"name": "3"}]) == 3
    assert niri_focus_user_time({"focus_timestamp": {"secs": 2, "nanos": 5}}) == 2_000_000_005
    assert niri_focus_user_time({"is_focused": True}) == 1
    assert niri_focus_user_time({}) == 0
    assert niri_current_desktop([{"id": 8, "idx": 1}, {"id": 9, "idx": 2, "is_focused": True}]) == 1
    assert niri_current_desktop([{"id": 8, "idx": 1, "is_focused": True}]) == 0
    assert niri_current_desktop([{"id": 8, "name": "code", "is_focused": True}]) == "code"
    assert niri_current_desktop([]) is None
    assert i3ipc_current_desktop([{"name": "1", "num": 1}, {"name": "5", "num": 5, "focused": True}]) == 4
    assert i3ipc_current_desktop([{"name": "code", "focused": True}]) == "code"
    assert i3ipc_current_desktop([{"name": "__i3_scratch", "focused": True}]) is None
    assert hypr_current_desktop({"id": 3, "name": "3"}) == 2
    assert hypr_current_desktop({"activeworkspace": {"id": 1}}) == 0
    assert hypr_current_desktop({"id": -98, "name": "special"}) == "special"
    assert qtile_current_desktop({"1": {"name": "1"}, "5": {"name": "5", "screen": 0}}) == 4
    assert qtile_current_desktop({"code": {"name": "code", "focused": True}}) == "code"
    assert qtile_current_desktop({"1": {"name": "1"}, "2": {"name": "2"}}) is None


def test_listed_workspace_count_uses_niri_when_ext_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setenv("NIRI_SOCKET", "/run/niri.sock")
    monkeypatch.setattr("ulauncher.modes.launcher.windows.shutil.which", lambda name: name if name == "niri" else None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._json_command",
        lambda argv: [{"id": 8, "idx": 1}, {"id": 9, "idx": 2}] if argv[-1] == "workspaces" else None,
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_desktop_count", lambda: 9)
    assert listed_workspace_count() == 2
    invalidate_workspace_count()


def test_listed_workspace_count_uses_qtile_when_ext_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "qtile")
    monkeypatch.setattr("ulauncher.modes.launcher.windows.shutil.which", lambda name: name if name == "qtile" else None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._json_command",
        lambda argv: {"1": {"name": "1"}, "4": {"name": "4"}} if argv[-1] == "groups" else None,
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_desktop_count", lambda: 9)
    assert listed_workspace_count() == 4
    invalidate_workspace_count()


def test_listed_current_desktop_prefers_ext_then_wmctrl(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr(
        "ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces",
        lambda: [
            {"removed": False, "state": 0, "coordinates": [0], "name": "1"},
            {"removed": False, "state": 1, "coordinates": [1], "name": "2"},
        ],
    )
    assert listed_current_desktop() == 1
    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.shutil.which",
        lambda name: "wmctrl" if name == "wmctrl" else None,
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._text_command",
        lambda _argv: "0  - DG: 1x1  VP: 0,0  WA: 0,0 1x1  1\n1  * DG: 1x1  VP: 0,0  WA: 0,0 1x1  2\n",
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_current_desktop", lambda: 9)
    assert listed_current_desktop() == 1
    invalidate_workspace_count()


def test_listed_current_desktop_uses_niri_when_ext_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setenv("NIRI_SOCKET", "/run/niri.sock")
    monkeypatch.setattr("ulauncher.modes.launcher.windows.shutil.which", lambda name: name if name == "niri" else None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._json_command",
        lambda argv: (
            [{"id": 8, "idx": 1}, {"id": 9, "idx": 2, "is_focused": True}] if argv[-1] == "workspaces" else None
        ),
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_current_desktop", lambda: 9)
    assert listed_current_desktop() == 1
    invalidate_workspace_count()


def test_listed_current_desktop_uses_qtile_when_ext_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "qtile")
    monkeypatch.setattr("ulauncher.modes.launcher.windows.shutil.which", lambda name: name if name == "qtile" else None)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._json_command",
        lambda argv: {"1": {"name": "1"}, "4": {"name": "4", "screen": 0}} if argv[-1] == "groups" else None,
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_current_desktop", lambda: 9)
    assert listed_current_desktop() == 3
    invalidate_workspace_count()


def test_listed_current_desktop_uses_hypr_when_ext_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.launcher.windows import invalidate_workspace_count

    invalidate_workspace_count()
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.list_ext_workspaces", lambda: None)
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "sig")
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows.shutil.which",
        lambda name: name if name == "hyprctl" else None,
    )
    monkeypatch.setattr(
        "ulauncher.modes.launcher.windows._json_command",
        lambda argv: {"id": 3, "name": "3"} if argv[-1] == "activeworkspace" else None,
    )
    monkeypatch.setattr("ulauncher.modes.launcher.windows._ewmh_current_desktop", lambda: 9)
    assert listed_current_desktop() == 2
    invalidate_workspace_count()


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
    ext_i = next(i for i, step in enumerate(steps) if step["kind"] == "ext-workspace")
    wmctrl_i = next(i for i, step in enumerate(steps) if step.get("argv") == ["wmctrl", "-s", "2"])
    assert steps[ext_i]["index"] == 2
    assert ext_i < wmctrl_i


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


def test_wayland_workspace_switch_uses_ext_workspace_before_wmctrl() -> None:
    ran: list[list[str]] = []

    def run(argv: list[str]) -> bool:
        ran.append(argv)
        return True

    used = switch_workspace(
        1,
        x11=False,
        which=lambda name: name if name == "wmctrl" else None,
        run=run,
        kwin=lambda _desktop: False,
        ewmh=lambda _index: False,
        ext_workspace=lambda index: index == 1,
    )
    assert used == "ext-workspace"
    assert ran == []
    used = switch_workspace(
        1,
        x11=False,
        which=lambda name: name if name == "wmctrl" else None,
        run=run,
        kwin=lambda _desktop: False,
        ewmh=lambda _index: False,
        ext_workspace=lambda _index: False,
    )
    assert used == "wmctrl"
    assert ran == [["wmctrl", "-s", "1"]]
    x_steps = workspace_switch_steps(1, x11=True)
    x_wmctrl = next(i for i, step in enumerate(x_steps) if step.get("argv") == ["wmctrl", "-s", "1"])
    x_ext = next(i for i, step in enumerate(x_steps) if step["kind"] == "ext-workspace")
    assert x_wmctrl < x_ext


def test_lswt_csv_lists_ext_foreign_toplevels() -> None:
    rows = windows_from_lswt_csv('Firefox,firefox,ext-1\n"Notes, 1",org.gnome.TextEditor,ext-2\n,,\n')
    assert [row.app_id for row in rows] == ["firefox", "org.gnome.TextEditor"]
    assert rows[1].title == "Notes, 1"
    assert rows[0].wid == "lswt:ext-1"
    assert compositor_window_argv(rows[0].wid, "focus") is None


def test_ext_foreign_handles_list_gnome_wayland_toplevels() -> None:
    rows = windows_from_ext_foreign_handles(
        [
            {"identifier": "gen-1", "title": "Mozilla Firefox", "app_id": "org.mozilla.firefox"},
            {"identifier": "", "title": "No id", "app_id": "x"},
            {"title": "Notes", "app_id": "org.gnome.TextEditor"},
            {"identifier": "gen-2", "title": "", "app_id": ""},
            {"identifier": "gen-3", "title": "Settings", "app_id": "org.gnome.Settings"},
        ]
    )
    assert [row.wid for row in rows] == ["ext:gen-1", "ext:gen-3"]
    assert rows[0].wm_class == "org.mozilla.firefox"
    assert window_matches(rows[0], "mozilla")
    assert compositor_window_argv(rows[0].wid, "focus") is None
    assert windows_from_ext_foreign_handles(None) == []


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
    desk = windows_from_kwin_dump([{"id": "{d2}", "title": "Code", "app_id": "code", "desktop": 2, "pid": 44}])
    assert desk[0].desktop == 1
    assert desk[0].pid == 44
    assert window_matches(desk[0], "workspace 2")
    sticky = windows_from_kwin_dump(
        [{"id": "{all}", "title": "Notes", "app_id": "kate", "desktop": -1, "onAllDesktops": True}]
    )
    assert sticky[0].sticky is True
    assert window_matches(sticky[0], "sticky")
    assert "desktop: desktopOf(c)" in KWIN_LIST_SCRIPT
    assert "pid: Number(c.pid || 0)" in KWIN_LIST_SCRIPT


def test_compositor_skip_taskbar_counts_for_apps_not_search() -> None:
    hypr = windows_from_hypr_clients(
        [
            {"address": "0x1", "title": "Firefox", "class": "firefox", "mapped": True},
            {"address": "0xhid", "title": "Hidden", "class": "firefox", "hidden": True},
            {"address": "0xunmapped", "title": "Gone", "class": "x", "mapped": False},
        ]
    )
    assert [row.title for row in hypr] == ["Firefox", "Hidden"]
    assert hypr[0].skip_taskbar is False
    assert hypr[1].skip_taskbar is True
    assert not window_is_searchable(hypr[1])
    assert "skipTaskbar: Boolean(c.skipTaskbar)" in KWIN_LIST_SCRIPT
    assert "c.skipTaskbar || c.desktopWindow" not in KWIN_LIST_SCRIPT
    hidden = windows_from_kwin_dump([{"id": "{panel}", "title": "Panel", "app_id": "plasmashell", "skipTaskbar": True}])
    assert hidden[0].skip_taskbar is True
    assert not window_is_searchable(hidden[0])
    assert (
        windows_from_kwin_dump([{"id": "{desk}", "title": "Desktop", "app_id": "plasmashell", "desktopWindow": True}])
        == []
    )


def test_sway_scratchpad_and_qtile_minimized_are_skip_taskbar() -> None:
    sway = windows_from_sway_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "__i3_scratch",
                    "floating_nodes": [
                        {"id": 9, "type": "floating_con", "name": "Notes", "app_id": "notes", "pid": 3},
                    ],
                }
            ],
        }
    )
    assert len(sway) == 1
    assert sway[0].skip_taskbar is True
    assert sway[0].desktop == -1
    assert not window_is_searchable(sway[0])
    marked = windows_from_i3_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "1",
                    "nodes": [
                        {
                            "id": 4,
                            "type": "con",
                            "name": "Vim",
                            "app_id": "vim",
                            "pid": 5,
                            "scratchpad_state": "fresh",
                        }
                    ],
                }
            ],
        }
    )
    assert marked[0].skip_taskbar is True
    qtile = windows_from_qtile_windows([{"id": 2, "name": "Hidden", "wm_class": "x", "minimized": True, "group": "1"}])
    assert qtile[0].skip_taskbar is True
    assert not window_is_searchable(qtile[0])


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


def test_named_sway_i3_qtile_workspaces_are_not_workspace_one() -> None:
    assert workspace_desktop_from_name("3") == 2
    assert workspace_desktop_from_name("code") == -1
    assert workspace_desktop_from_name("2:www") == 1
    assert workspace_desktop_from_name("www", 3) == 2
    assert workspace_desktop_from_name("code", -1) == -1
    assert workspace_desktop_from_name("code", True) == -1
    assert workspace_desktop_from_name("", "2") == 1
    assert workspace_desktop_from_name("code", "3") == 2

    sway = windows_from_sway_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "code",
                    "nodes": [
                        {
                            "id": 7,
                            "type": "con",
                            "name": "Editor",
                            "app_id": "code",
                            "pid": 3,
                        }
                    ],
                }
            ],
        }
    )
    assert sway[0].desktop == -1
    assert window_workspace_label(sway[0].desktop) == "Switch to window"
    assert not window_matches(sway[0], "1")
    assert not window_matches(sway[0], "workspace 1")

    i3 = windows_from_i3_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "2:www",
                    "nodes": [
                        {
                            "id": 9,
                            "type": "con",
                            "name": "Firefox",
                            "window_properties": {"class": "firefox", "title": "Firefox"},
                            "pid": 4,
                        }
                    ],
                }
            ],
        }
    )
    assert i3[0].desktop == 1
    assert window_matches(i3[0], "2")
    assert not window_matches(i3[0], "1")

    i3_num = windows_from_i3_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "type": "workspace",
                    "name": "www",
                    "num": 3,
                    "nodes": [
                        {
                            "id": 10,
                            "type": "con",
                            "name": "Chrome",
                            "window_properties": {"class": "google-chrome"},
                            "pid": 5,
                        }
                    ],
                }
            ],
        }
    )
    assert i3_num[0].desktop == 2

    qtile = windows_from_qtile_windows([{"id": 1, "name": "Term", "wm_class": "foot", "group": "code"}])
    assert qtile[0].desktop == -1
    assert window_workspace_label(qtile[0].desktop) == "Switch to window"
    assert not window_matches(qtile[0], "1")


def test_missing_hypr_niri_workspace_is_not_workspace_one() -> None:
    named = windows_from_hypr_clients(
        [
            {
                "address": "0xcode",
                "title": "Editor",
                "class": "code",
                "workspace": {"name": "code"},
                "mapped": True,
            }
        ]
    )
    assert named[0].desktop == -1
    assert window_workspace_label(named[0].desktop) == "Switch to window"
    assert not window_matches(named[0], "1")

    string_id = windows_from_hypr_clients(
        [
            {
                "address": "0xnum",
                "title": "Term",
                "class": "foot",
                "workspace": {"id": "2"},
                "mapped": True,
            }
        ]
    )
    assert string_id[0].desktop == 1
    assert window_matches(string_id[0], "2")

    special_str = windows_from_hypr_clients(
        [
            {
                "address": "0xneg",
                "title": "Scratch",
                "class": "foot",
                "workspace": {"id": "-98"},
                "mapped": True,
            }
        ]
    )
    assert special_str[0].desktop == -1
    assert not window_matches(special_str[0], "1")

    text_ws = windows_from_hypr_clients(
        [
            {
                "address": "0xstr",
                "title": "Term",
                "class": "foot",
                "workspace": "code",
                "mapped": True,
            }
        ]
    )
    assert text_ws[0].desktop == -1
    assert not window_matches(text_ws[0], "1")

    niri = windows_from_niri_windows([{"id": 9, "title": "Notes", "app_id": "notes"}])
    assert niri[0].desktop == -1
    assert not window_matches(niri[0], "1")

    niri_named = windows_from_niri_windows([{"id": 10, "title": "Web", "app_id": "firefox", "workspace_id": "code"}])
    assert niri_named[0].desktop == -1

    niri_idx = windows_from_niri_windows(
        [{"id": 7, "title": "Notes", "app_id": "notes", "workspace_id": 8}],
        [{"id": 8, "idx": 1, "name": "code"}],
    )
    assert niri_idx[0].desktop == 0
    assert window_matches(niri_idx[0], "1")
    assert not window_matches(niri_idx[0], "8")

    niri_second = windows_from_niri_windows(
        [{"id": 9, "title": "Web", "app_id": "firefox", "workspace_id": 8}],
        [{"id": 3, "idx": 1}, {"id": 8, "idx": 2}],
    )
    assert niri_second[0].desktop == 1
    assert window_matches(niri_second[0], "2")

    niri_missing_ws = windows_from_niri_windows(
        [{"id": 11, "title": "Ghost", "app_id": "ghost", "workspace_id": 99}],
        [{"id": 8, "idx": 1}],
    )
    assert niri_missing_ws[0].desktop == -1
    assert not window_matches(niri_missing_ws[0], "1")

    stray = windows_from_sway_tree(
        {
            "type": "root",
            "nodes": [
                {
                    "id": 1,
                    "type": "con",
                    "name": "Ghost",
                    "app_id": "ghost",
                    "pid": 2,
                }
            ],
        }
    )
    assert stray[0].desktop == -1
    assert not window_matches(stray[0], "workspace 1")


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


def test_match_windows_hides_skip_taskbar() -> None:
    listed = WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox", desktop=0, pid=11)
    hidden = WindowInfo(
        wid="0x2",
        title="Mozilla Firefox",
        wm_class="firefox",
        desktop=0,
        pid=11,
        skip_taskbar=True,
    )
    dock = WindowInfo(wid="0x3", title="Dock", wm_class="dock", desktop=0, pid=1, window_type="dock")
    rows = match_windows("firefox", windows=[hidden, listed, dock])
    assert [row["wid"] for row in rows] == ["0x1"]
    assert window_is_searchable(listed)
    assert not window_is_searchable(hidden)
    assert not window_is_searchable(dock)
    assert match_windows("dock", windows=[dock]) == []


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
