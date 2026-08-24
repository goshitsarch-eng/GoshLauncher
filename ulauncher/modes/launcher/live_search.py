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
        self._bus: Any = None
        self._windows_changed_id = 0

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._fingerprint = windows_fingerprint(self._current_windows())
        self._listen_apps()
        self._listen_shell_windows()
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
        self._unlisten_shell_windows()
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

    def _listen_shell_windows(self) -> None:
        # goshos uses global.display window-created; GTK gets WindowsChanged from Mutter introspect
        try:
            from ulauncher.gi import Gio

            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._windows_changed_id = bus.signal_subscribe(
                "org.gnome.Shell.Introspect",
                "org.gnome.Shell.Introspect",
                "WindowsChanged",
                "/org/gnome/Shell/Introspect",
                None,
                Gio.DBusSignalFlags.NONE,
                lambda *_args: self._on_change(),
            )
            self._bus = bus
        except (AttributeError, TypeError, RuntimeError, OSError, ValueError):
            self._windows_changed_id = 0
            self._bus = None

    def _unlisten_shell_windows(self) -> None:
        if self._bus is not None and self._windows_changed_id:
            with contextlib.suppress(TypeError, RuntimeError, OSError, AttributeError):
                self._bus.signal_unsubscribe(self._windows_changed_id)
        self._bus = None
        self._windows_changed_id = 0
