"""X11 stand-in for goshos liveSearchWatcher window and workspace signals.

Mutter emits window-created, unmanaged, active-workspace-changed, and
notify::n-workspaces. EWMH exposes the same as PropertyNotify on the root
window. python-xlib is imported only when the watch starts so tests that never
open a Display do not need it installed.
"""

from __future__ import annotations

import contextlib
import importlib
from collections.abc import Mapping
from typing import Any, Callable

# X.PropertyNotify. Hard-coded so drain tests do not import python-xlib.
X11_PROPERTY_NOTIFY = 28

# goshos liveSearchWatcher: window-created / unmanaged, n-workspaces,
# active-workspace-changed. _NET_ACTIVE_WINDOW also covers same-class focus
# recency, which Introspect WindowsChanged does not emit.
X11_LIVE_ATOMS = (
    "_NET_CURRENT_DESKTOP",
    "_NET_NUMBER_OF_DESKTOPS",
    "_NET_ACTIVE_WINDOW",
    "_NET_CLIENT_LIST",
    "_NET_CLIENT_LIST_STACKING",
)


def is_x11_live_atom(name: str) -> bool:
    return name in X11_LIVE_ATOMS


def intern_x11_live_atoms(display: Any) -> dict[int, str]:
    interned: dict[int, str] = {}
    for name in X11_LIVE_ATOMS:
        interned[int(display.intern_atom(name))] = name
    return interned


def x11_display_fileno(display: Any) -> int:
    if hasattr(display, "fileno"):
        return int(display.fileno())
    return int(display.display.socket.fileno())


def drain_x11_live_events(display: Any, interned: Mapping[int, str]) -> bool:
    """True when a drained PropertyNotify is one of the live-search atoms."""
    changed = False
    while display.pending_events():
        event = display.next_event()
        if getattr(event, "type", None) != X11_PROPERTY_NOTIFY:
            continue
        atom = getattr(event, "atom", None)
        if isinstance(atom, int) and interned.get(atom):
            changed = True
    return changed


class X11LiveWatch:
    """Root-window PropertyNotify → on_change. No-op when Xlib or DISPLAY is missing."""

    def __init__(self) -> None:
        self._display: Any = None
        self._atoms: dict[int, str] = {}
        self._source: Any = None
        self._on_change: Callable[[], None] | None = None

    def start(self, on_change: Callable[[], None]) -> bool:
        if self._display is not None:
            return True
        try:
            # importlib so pyrefly does not require python-xlib in every venv
            # (CI images have it; some local venvs do not).
            x_mod = importlib.import_module("Xlib.X")
            xdisplay = importlib.import_module("Xlib.display")
        except ImportError:
            return False
        dpy = None
        try:
            dpy = xdisplay.Display()
            dpy.screen().root.change_attributes(event_mask=x_mod.PropertyChangeMask)
            dpy.flush()
            atoms = intern_x11_live_atoms(dpy)
            fd = x11_display_fileno(dpy)
        except Exception:
            # Xlib DisplayError is a bare Exception; a failed probe must not
            # take down popup open.
            if dpy is not None:
                with contextlib.suppress(OSError, RuntimeError, TypeError):
                    dpy.close()
            return False
        self._on_change = on_change
        self._display = dpy
        self._atoms = atoms
        try:
            from ulauncher.utils.scheduling import watch_fd

            self._source = watch_fd(fd, self._on_readable)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            self._display = None
            self._atoms = {}
            self._on_change = None
            with contextlib.suppress(OSError, RuntimeError, TypeError):
                dpy.close()
            return False
        return True

    def stop(self) -> None:
        if self._source is not None:
            self._source.cancel()
            self._source = None
        if self._display is not None:
            with contextlib.suppress(OSError, RuntimeError, TypeError):
                self._display.close()
            self._display = None
        self._atoms = {}
        self._on_change = None

    def _on_readable(self) -> None:
        display = self._display
        on_change = self._on_change
        if display is None or on_change is None:
            return
        try:
            changed = drain_x11_live_events(display, self._atoms)
        except (OSError, RuntimeError, TypeError, ValueError):
            return
        if changed:
            on_change()
