"""Refresh launcher rows while the popup is open when windows or apps change."""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from ulauncher.modes.launcher.search_live import windows_fingerprint, windows_for_live_track
from ulauncher.utils import scheduling

_POLL_SEC = 0.8


class LiveSearchWatcher:
    def __init__(
        self,
        on_change: Callable[[], None],
        list_windows: Callable[[], list[Any]] | None = None,
        poll_interval: float = _POLL_SEC,
    ) -> None:
        self._on_change = on_change
        self._list_windows = list_windows
        self._poll_interval = poll_interval
        self._listening = False
        self._timer: scheduling.Context | None = None
        self._apps: Any = None
        self._apps_handler = 0
        self._fingerprint: tuple[tuple[Any, ...], ...] = ()

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._fingerprint = windows_fingerprint(self._current_windows())
        self._listen_apps()
        if self._poll_interval > 0:
            self._timer = scheduling.interval(self._poll_interval, self.poll)

    def stop(self) -> None:
        if not self._listening:
            return
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._apps is not None and self._apps_handler:
            with contextlib.suppress(TypeError, RuntimeError):
                self._apps.disconnect(self._apps_handler)
        self._apps = None
        self._apps_handler = 0
        self._fingerprint = ()
        self._listening = False

    def poll(self) -> None:
        if not self._listening:
            return
        fingerprint = windows_fingerprint(self._current_windows())
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        self._on_change()

    def _current_windows(self) -> list[Any]:
        list_fn = self._list_windows
        if list_fn is None:
            from ulauncher.modes.launcher.windows import list_windows

            list_fn = list_windows
        return windows_for_live_track(list_fn)

    def _listen_apps(self) -> None:
        try:
            from ulauncher.gi import Gio

            monitor = Gio.AppInfoMonitor.get()
        except (AttributeError, TypeError, RuntimeError, OSError):
            return
        self._apps = monitor
        try:
            self._apps_handler = monitor.connect("changed", lambda *_args: self._on_change())
        except (TypeError, RuntimeError):
            self._apps = None
            self._apps_handler = 0
