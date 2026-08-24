from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.live_search import LiveSearchWatcher


def test_watcher_notifies_when_window_list_changes() -> None:
    windows: list[SimpleNamespace] = []
    events: list[int] = []
    watcher = LiveSearchWatcher(lambda: events.append(1), list_windows=lambda: list(windows), poll_interval=0)
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
