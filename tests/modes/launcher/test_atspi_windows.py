from __future__ import annotations

from ulauncher.modes.launcher.atspi_windows import (
    AtspiLiveWatch,
    atspi_focus_ranks,
    atspi_ref,
    atspi_role_is_listed,
    atspi_role_is_skip_taskbar,
    atspi_window_type,
    grab_atspi_focus,
    note_atspi_focus,
    reset_atspi_focus_history,
    split_atspi_ref,
    windows_from_atspi_nodes,
)


def test_atspi_roles_match_goshos_listed_types() -> None:
    assert atspi_role_is_listed("frame") is True
    assert atspi_role_is_listed("dialog") is True
    assert atspi_role_is_listed("panel") is False
    assert atspi_role_is_skip_taskbar("panel") is True
    assert atspi_role_is_skip_taskbar("notification") is True
    assert atspi_window_type("dialog") == "dialog"
    assert atspi_window_type("panel") == "dock"
    assert atspi_window_type("frame") == "normal"


def test_windows_from_atspi_nodes_keep_skip_taskbar_chrome() -> None:
    rows = windows_from_atspi_nodes(
        [
            {
                "role": "frame",
                "title": "Firefox",
                "app_id": "firefox",
                "bus_name": ":1.2",
                "path": "/w/1",
                "active": True,
            },
            {"role": "panel", "title": "Dash", "app_id": "dash", "bus_name": ":1.3", "path": "/w/2"},
            {"role": "label", "title": "Ignore"},
            {"role": "frame", "title": ""},
        ]
    )
    assert [row.title for row in rows] == ["Firefox", "Dash"]
    assert rows[0].user_time == 1
    assert rows[0].skip_taskbar is False
    assert rows[0].atspi_ref == atspi_ref(":1.2", "/w/1")
    assert rows[1].skip_taskbar is True
    assert rows[1].window_type == "dock"
    assert split_atspi_ref(rows[0].atspi_ref) == (":1.2", "/w/1")
    assert split_atspi_ref("nope") is None


def test_atspi_focus_history_ranks_like_get_tab_list() -> None:
    reset_atspi_focus_history()
    try:
        note_atspi_focus("Old", "old")
        note_atspi_focus("Front", "firefox")
        ranks = atspi_focus_ranks()
        assert ranks["front"] == 0
        assert ranks["firefox"] == 1
        assert ranks["old"] > ranks["front"]
    finally:
        reset_atspi_focus_history()


def test_grab_atspi_focus_prefers_ref_then_title() -> None:
    grabbed: list[str] = []

    def grab(ref: str) -> bool:
        grabbed.append(ref)
        return True

    assert grab_atspi_focus(atspi_ref(":1.2", "/w/1"), grab=grab, find_ref=lambda *_args: "") is True
    assert grabbed == [atspi_ref(":1.2", "/w/1")]
    grabbed.clear()
    assert grab_atspi_focus("", "Firefox", "firefox", grab=grab, find_ref=lambda title, app: f"{title}:{app}") is True
    assert grabbed == ["Firefox:firefox"]
    assert grab_atspi_focus("", grab=grab, find_ref=lambda *_args: "") is False


def test_atspi_live_watch_records_activate_and_notifies() -> None:
    reset_atspi_focus_history()
    events: list[int] = []
    callbacks: list[object] = []

    class _Conn:
        def signal_subscribe(self, *_args: object, **_kwargs: object) -> int:
            callback = _kwargs.get("callback")
            if callback is None and len(_args) >= 7:
                callback = _args[6]
            if callback is not None:
                callbacks.append(callback)
            return 7

        def signal_unsubscribe(self, *_args: object) -> None:
            return None

    watch = AtspiLiveWatch()
    try:
        assert watch.start(lambda: events.append(1), connection=_Conn()) is True
        assert callbacks
        activate = callbacks[0]
        assert callable(activate)
        activate(":1.2", None, "/w/1", "Activate")
        assert events == [1]
        activate(":1.2", None, "/w/1", "Create")
        assert events == [1, 1]
        watch.stop()
        activate(":1.2", None, "/w/1", "Destroy")
        assert events == [1, 1]
    finally:
        watch.stop()
        reset_atspi_focus_history()
