from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.live_search import INTROSPECT_WINDOW_WATCHES, LiveSearchWatcher


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


def test_introspect_window_watches_cover_both_shell_names() -> None:
    dests = {row[0] for row in INTROSPECT_WINDOW_WATCHES}
    assert dests == {"org.gnome.Shell.Introspect", "org.gnome.Shell"}
    for _dest, path, iface, member in INTROSPECT_WINDOW_WATCHES:
        assert path == "/org/gnome/Shell/Introspect"
        assert iface == "org.gnome.Shell.Introspect"
        assert member == "WindowsChanged"
