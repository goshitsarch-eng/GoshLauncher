"""Refresh launcher rows while the popup is open when windows or apps change."""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from ulauncher.modes.launcher.search_live import live_search_fingerprint, windows_for_live_track
from ulauncher.utils import scheduling

_POLL_SEC = 0.8

# goshos connects to global.display window-created. Mutter exports the same
# change as WindowsChanged on Introspect; some sessions own it on org.gnome.Shell.
INTROSPECT_WINDOW_WATCHES = (
    ("org.gnome.Shell.Introspect", "/org/gnome/Shell/Introspect", "org.gnome.Shell.Introspect", "WindowsChanged"),
    ("org.gnome.Shell", "/org/gnome/Shell/Introspect", "org.gnome.Shell.Introspect", "WindowsChanged"),
)


class LiveSearchWatcher:
    def __init__(
        self,
        on_change: Callable[[], None],
        list_windows: Callable[[], list[Any]] | None = None,
        poll_interval: float = _POLL_SEC,
        workspace_count: Callable[[], int | None] | None = None,
    ) -> None:
        self._on_change = on_change
        self._list_windows = list_windows
        self._poll_interval = poll_interval
        self._workspace_count = workspace_count
        self._listening = False
        self._timer: scheduling.Context | None = None
        self._apps: Any = None
        self._apps_handler = 0
        self._fingerprint: tuple[Any, ...] = ()
        self._bus: Any = None
        self._windows_changed_ids: list[int] = []

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._fingerprint = self._snapshot()
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
        self._invalidate_window_state()
        fingerprint = self._snapshot()
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        self._on_change()

    def _snapshot(self) -> tuple[Any, ...]:
        count_fn = self._workspace_count
        if count_fn is None:
            from ulauncher.modes.launcher.windows import listed_workspace_count

            count_fn = listed_workspace_count
        return live_search_fingerprint(self._current_windows(), count_fn())

    def _invalidate_window_state(self) -> None:
        from ulauncher.modes.launcher.windows import invalidate_windows, invalidate_workspace_count

        invalidate_windows()
        invalidate_workspace_count()

    def _notify(self) -> None:
        if not self._listening:
            return
        self._invalidate_window_state()
        self._fingerprint = self._snapshot()
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
            self._apps_handler = monitor.connect("changed", lambda *_args: self._notify())
        except (TypeError, RuntimeError):
            self._apps = None
            self._apps_handler = 0

    def _listen_shell_windows(self) -> None:
        # goshos uses global.display window-created; GTK gets WindowsChanged from Mutter introspect
        try:
            from ulauncher.gi import Gio

            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except (AttributeError, TypeError, RuntimeError, OSError, ValueError):
            self._windows_changed_ids = []
            self._bus = None
            return
        self._bus = bus
        self._windows_changed_ids = []
        for dest, path, iface, member in INTROSPECT_WINDOW_WATCHES:
            try:
                watch_id = bus.signal_subscribe(
                    dest,
                    iface,
                    member,
                    path,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    lambda *_args: self._notify(),
                )
            except (AttributeError, TypeError, RuntimeError, OSError, ValueError):
                continue
            if watch_id:
                self._windows_changed_ids.append(int(watch_id))

    def _unlisten_shell_windows(self) -> None:
        if self._bus is not None:
            for watch_id in self._windows_changed_ids:
                with contextlib.suppress(TypeError, RuntimeError, OSError, AttributeError):
                    self._bus.signal_unsubscribe(watch_id)
        self._bus = None
        self._windows_changed_ids = []
