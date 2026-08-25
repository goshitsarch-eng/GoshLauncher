from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.search_live import (
    live_search_fingerprint,
    next_live_search_action,
    should_track_live_window,
    windows_fingerprint,
    windows_for_live_track,
)


def test_next_live_search_action() -> None:
    assert next_live_search_action(False, True) == "start"
    assert next_live_search_action(True, False) == "stop"
    assert next_live_search_action(True, True) == "keep"
    assert next_live_search_action(False, False) == "keep"


def test_should_track_live_window() -> None:
    win = SimpleNamespace(wid="0x1")
    assert should_track_live_window(None, []) is False
    assert should_track_live_window(win, [win]) is False
    assert should_track_live_window(win, []) is True


def test_windows_for_live_track_drops_holes_and_throws() -> None:
    tracked = SimpleNamespace(wid="1")
    later = SimpleNamespace(wid="2")
    assert windows_for_live_track(lambda: [tracked, None, later]) == [tracked, later]
    assert windows_for_live_track(lambda: (_ for _ in ()).throw(RuntimeError("gone"))) == []
    assert windows_for_live_track(lambda: "nope") == []  # type: ignore[arg-type, return-value]


def test_windows_fingerprint_changes_with_title() -> None:
    first = [SimpleNamespace(wid="1", title="A", desktop=0, wm_class="x")]
    second = [SimpleNamespace(wid="1", title="B", desktop=0, wm_class="x")]
    assert windows_fingerprint(first) != windows_fingerprint(second)


def test_live_search_fingerprint_includes_workspace_count() -> None:
    windows = [SimpleNamespace(wid="1", title="A", desktop=0, wm_class="x")]
    same_windows = live_search_fingerprint(windows, 2)
    assert same_windows == live_search_fingerprint(windows, 2)
    assert live_search_fingerprint(windows, 3) != same_windows
    assert live_search_fingerprint([], 2) != same_windows
