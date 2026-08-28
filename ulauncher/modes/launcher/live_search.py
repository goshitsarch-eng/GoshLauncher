"""Refresh launcher rows while the popup is open when windows or apps change."""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from ulauncher.modes.launcher.search_live import live_search_fingerprint, windows_for_live_track
from ulauncher.utils import scheduling

# goshos liveSearchWatcher is signal-driven (0ms). This is the GTK stand-in
# while the popup is open: cheap enough to feel snappy, long enough to avoid
# hammering Introspect/compositor IPC on every frame.
LIVE_SEARCH_POLL_SEC = 0.25

# goshos connects to global.display window-created and Shell.AppSystem
# app-state-changed. Mutter exports those as WindowsChanged and
# RunningApplicationsChanged on Introspect; some sessions own it on org.gnome.Shell.
INTROSPECT_WINDOW_WATCHES = (
    ("org.gnome.Shell.Introspect", "/org/gnome/Shell/Introspect", "org.gnome.Shell.Introspect", "WindowsChanged"),
    ("org.gnome.Shell", "/org/gnome/Shell/Introspect", "org.gnome.Shell.Introspect", "WindowsChanged"),
)
INTROSPECT_RUNNING_WATCHES = (
    (
        "org.gnome.Shell.Introspect",
        "/org/gnome/Shell/Introspect",
        "org.gnome.Shell.Introspect",
        "RunningApplicationsChanged",
    ),
    ("org.gnome.Shell", "/org/gnome/Shell/Introspect", "org.gnome.Shell.Introspect", "RunningApplicationsChanged"),
)


class LiveSearchWatcher:
    def __init__(
        self,
        on_change: Callable[[], None],
        list_windows: Callable[[], list[Any]] | None = None,
        poll_interval: float = LIVE_SEARCH_POLL_SEC,
        workspace_count: Callable[[], int | None] | None = None,
        current_desktop: Callable[[], int | str | None] | None = None,
    ) -> None:
        self._on_change = on_change
        self._list_windows = list_windows
        self._poll_interval = poll_interval
        self._workspace_count = workspace_count
        self._current_desktop = current_desktop
        self._listening = False
        self._timer: scheduling.Context | None = None
        self._apps: Any = None
        self._apps_handler = 0
        self._fingerprint: tuple[Any, ...] = ()
        self._bus: Any = None
        self._windows_changed_ids: list[Any] = []
        self._x11: Any = None
        self._ext_ws: Any = None
        self._ext_list: Any = None
        self._atspi: Any = None

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
        self._listen_host_signals()
        if self._poll_interval > 0:
            self._timer = scheduling.interval(self._poll_interval, self.poll)

    def stop(self) -> None:
        if not self._listening:
            return
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._apps is not None:
            with contextlib.suppress(TypeError, RuntimeError):
                self._apps.directoryChanged.disconnect()
        self._unlisten_shell_windows()
        self._unlisten_host_signals()
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
        desktop_fn = self._current_desktop
        if count_fn is None or desktop_fn is None:
            from ulauncher.modes.launcher.windows import listed_current_desktop, listed_workspace_count

            if count_fn is None:
                count_fn = listed_workspace_count
            if desktop_fn is None:
                desktop_fn = listed_current_desktop
        return live_search_fingerprint(self._current_windows(), count_fn(), desktop_fn())

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
        # App installs/removals: watch the applications dirs directly.
        try:
            import os
            import sys

            qt_core = sys.modules.get("PySide6.QtCore")
            if qt_core is None or qt_core.QCoreApplication.instance() is None:
                return
            from ulauncher.utils.desktop_entry import _application_dirs

            watcher = qt_core.QFileSystemWatcher([d for d in _application_dirs() if os.path.isdir(d)])
            watcher.directoryChanged.connect(lambda *_args: self._notify())
        except (AttributeError, TypeError, RuntimeError, OSError):
            return
        self._apps = watcher

    def _listen_shell_windows(self) -> None:
        # goshos uses window-created and AppSystem app-state-changed; we get
        # WindowsChanged and RunningApplicationsChanged from Mutter introspect
        self._windows_changed_ids = []
        try:
            from ulauncher.utils import qdbus

            bus = qdbus.session_bus()
        except (AttributeError, TypeError, RuntimeError, OSError, ValueError, ImportError):
            self._bus = None
            return
        self._bus = bus
        subscriptions = []
        for dest, path, iface, member in INTROSPECT_WINDOW_WATCHES + INTROSPECT_RUNNING_WATCHES:
            try:
                subscription = qdbus.subscribe(bus, dest, path, iface, member, lambda *_args: self._notify())
            except (AttributeError, TypeError, RuntimeError, OSError, ValueError):
                continue
            if subscription is not None:
                subscriptions.append(subscription)
        self._windows_changed_ids = subscriptions

    def _unlisten_shell_windows(self) -> None:
        for subscription in self._windows_changed_ids:
            with contextlib.suppress(TypeError, RuntimeError, OSError, AttributeError):
                subscription.unsubscribe()
        self._bus = None
        self._windows_changed_ids = []

    def _listen_host_signals(self) -> None:
        # goshos connects to workspace_manager and per-window unmanaged. GTK
        # stand-ins: EWMH PropertyNotify on X11, ext-workspace-v1 and
        # ext-foreign-toplevel-list on Wayland, AT-SPI Window events when a11y
        # is already enabled.
        from ulauncher.modes.launcher.atspi_windows import AtspiLiveWatch
        from ulauncher.modes.launcher.wayland_toplevels import ExtForeignLiveWatch
        from ulauncher.modes.launcher.wayland_workspaces import ExtWorkspaceLiveWatch
        from ulauncher.modes.launcher.x11_live import X11LiveWatch

        x11 = X11LiveWatch()
        if x11.start(self._notify):
            self._x11 = x11
        ext_ws = ExtWorkspaceLiveWatch()
        if ext_ws.start(self._notify):
            self._ext_ws = ext_ws
        ext_list = ExtForeignLiveWatch()
        if ext_list.start(self._notify):
            self._ext_list = ext_list
        atspi = AtspiLiveWatch()
        if atspi.start(self._notify):
            self._atspi = atspi

    def _unlisten_host_signals(self) -> None:
        if self._x11 is not None:
            with contextlib.suppress(AttributeError, OSError, RuntimeError, TypeError):
                self._x11.stop()
            self._x11 = None
        if self._ext_ws is not None:
            with contextlib.suppress(AttributeError, OSError, RuntimeError, TypeError):
                self._ext_ws.stop()
            self._ext_ws = None
        if self._ext_list is not None:
            with contextlib.suppress(AttributeError, OSError, RuntimeError, TypeError):
                self._ext_list.stop()
            self._ext_list = None
        if self._atspi is not None:
            with contextlib.suppress(AttributeError, OSError, RuntimeError, TypeError):
                self._atspi.stop()
            self._atspi = None
