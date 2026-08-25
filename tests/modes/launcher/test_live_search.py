from __future__ import annotations

from types import SimpleNamespace

import pytest

from ulauncher.modes.launcher.live_search import (
    INTROSPECT_RUNNING_WATCHES,
    INTROSPECT_WINDOW_WATCHES,
    LIVE_SEARCH_POLL_SEC,
    LiveSearchWatcher,
)


def test_watcher_notifies_when_window_list_changes() -> None:
    windows: list[SimpleNamespace] = []
    events: list[int] = []
    watcher = LiveSearchWatcher(
        lambda: events.append(1),
        list_windows=lambda: list(windows),
        poll_interval=0,
        workspace_count=lambda: 2,
        current_desktop=lambda: 0,
    )
    watcher.start()
    assert watcher.listening is True
    assert events == []
    windows.append(SimpleNamespace(wid="1", title="Term", desktop=0, wm_class="kgx"))
    watcher.poll()
    assert events == [1]
    watcher.poll()
    assert events == [1]
    watcher.stop()
    assert watcher.listening is False
    watcher.poll()
    assert events == [1]


def test_watcher_notifies_when_workspace_count_changes() -> None:
    count = {"n": 2}
    events: list[int] = []
    watcher = LiveSearchWatcher(
        lambda: events.append(1),
        list_windows=list,
        poll_interval=0,
        workspace_count=lambda: count["n"],
        current_desktop=lambda: 0,
    )
    watcher.start()
    watcher.poll()
    assert events == []
    count["n"] = 3
    watcher.poll()
    assert events == [1]


def test_watcher_notifies_when_current_desktop_changes() -> None:
    desktop = {"n": 0}
    events: list[int] = []
    watcher = LiveSearchWatcher(
        lambda: events.append(1),
        list_windows=list,
        poll_interval=0,
        workspace_count=lambda: 2,
        current_desktop=lambda: desktop["n"],
    )
    watcher.start()
    watcher.poll()
    assert events == []
    desktop["n"] = 1
    watcher.poll()
    assert events == [1]


def test_watcher_notifies_when_window_recency_changes() -> None:
    windows = [SimpleNamespace(wid="1", title="Term", desktop=0, wm_class="kgx", user_time=1)]
    events: list[int] = []
    watcher = LiveSearchWatcher(
        lambda: events.append(1),
        list_windows=lambda: list(windows),
        poll_interval=0,
        workspace_count=lambda: 2,
        current_desktop=lambda: 0,
    )
    watcher.start()
    watcher.poll()
    assert events == []
    windows[0].user_time = 9
    watcher.poll()
    assert events == [1]


def test_default_poll_is_faster_than_a_second() -> None:
    assert 0 < LIVE_SEARCH_POLL_SEC <= 0.3


def test_introspect_window_watches_cover_both_shell_names() -> None:
    dests = {row[0] for row in INTROSPECT_WINDOW_WATCHES}
    assert dests == {"org.gnome.Shell.Introspect", "org.gnome.Shell"}
    for _dest, path, iface, member in INTROSPECT_WINDOW_WATCHES:
        assert path == "/org/gnome/Shell/Introspect"
        assert iface == "org.gnome.Shell.Introspect"
        assert member == "WindowsChanged"


def test_introspect_running_watches_cover_both_shell_names() -> None:
    dests = {row[0] for row in INTROSPECT_RUNNING_WATCHES}
    assert dests == {"org.gnome.Shell.Introspect", "org.gnome.Shell"}
    for _dest, path, iface, member in INTROSPECT_RUNNING_WATCHES:
        assert path == "/org/gnome/Shell/Introspect"
        assert iface == "org.gnome.Shell.Introspect"
        assert member == "RunningApplicationsChanged"


def test_watcher_starts_x11_and_wayland_host_listeners(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    stopped: list[str] = []

    class _X11:
        def start(self, _on_change: object) -> bool:
            started.append("x11")
            return True

        def stop(self) -> None:
            stopped.append("x11")

    class _Ext:
        def start(self, _on_change: object) -> bool:
            started.append("ext")
            return True

        def stop(self) -> None:
            stopped.append("ext")

    class _Foreign:
        def start(self, _on_change: object) -> bool:
            started.append("foreign")
            return True

        def stop(self) -> None:
            stopped.append("foreign")

    monkeypatch.setattr("ulauncher.modes.launcher.x11_live.X11LiveWatch", _X11)
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.ExtWorkspaceLiveWatch", _Ext)
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_toplevels.ExtForeignLiveWatch", _Foreign)
    watcher = LiveSearchWatcher(
        lambda: None,
        list_windows=list,
        poll_interval=0,
        workspace_count=lambda: 1,
        current_desktop=lambda: 0,
    )
    watcher.start()
    assert started == ["x11", "ext", "foreign"]
    watcher.stop()
    assert stopped == ["x11", "ext", "foreign"]
