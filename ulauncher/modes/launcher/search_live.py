"""When to watch windows and apps for a live repaint, from spotlight-goshos searchLive.js."""

from __future__ import annotations

from typing import Any, Callable


def next_live_search_action(was_listening: bool, want_listening: bool) -> str:
    if want_listening and not was_listening:
        return "start"
    if not want_listening and was_listening:
        return "stop"
    return "keep"


def should_track_live_window(win: Any, tracked: list[Any]) -> bool:
    if not win:
        return False
    return win not in tracked


def windows_for_live_track(list_fn: Callable[[], Any]) -> list[Any]:
    try:
        windows = list_fn()
    except Exception:
        return []
    if not isinstance(windows, list):
        return []
    return [win for win in windows if win]


def windows_fingerprint(windows: list[Any]) -> tuple[tuple[Any, ...], ...]:
    rows = []
    for win in windows:
        rows.append(
            (
                getattr(win, "wid", None),
                getattr(win, "title", None),
                getattr(win, "desktop", None),
                getattr(win, "wm_class", None),
            )
        )
    return tuple(rows)


def live_search_fingerprint(windows: list[Any], workspace_count: int | None) -> tuple[Any, ...]:
    """goshos liveSearchWatcher also repaints on notify::n-workspaces."""
    return (workspace_count, windows_fingerprint(windows))
