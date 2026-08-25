"""IME lookup-table visibility, ported from spotlight-goshos entryPreedit.js.

GNOME Shell walks ``uiGroup`` for ``candidate-popup-boxpointer``. GTK has no
St actor tree, so an IBus/Fcitx candidate window is the public stand-in.
"""

from __future__ import annotations

import time
from typing import Any

from ulauncher.modes.launcher.windows import WindowInfo

# ibus-ui-gtk* and fcitx candidate frames; prefs windows stay off this list
_PANEL_MARKERS = (
    "ibus-ui-gtk",
    "ibus-ui-gtk3",
    "ibus-ui-gtk4",
    "org.freedesktop.ibus.panel",
    "ibuspanel",
    "fcitx-candidate",
    "org.fcitx.fcitx5.virtualkeyboard",
)

_PANEL_CACHE: dict[str, Any] = {"monotonic": 0.0, "visible": False}
_CACHE_TTL_S = 0.1


def _blob(win: WindowInfo) -> str:
    return f"{win.wm_class} {win.app_id} {win.title}".lower()


def is_ime_panel_window(win: WindowInfo) -> bool:
    blob = _blob(win)
    compact = blob.replace(" ", "")
    for marker in _PANEL_MARKERS:
        if marker in blob or marker.replace(".", "") in compact:
            return True
    if "candidate" in blob or "lookup" in blob:
        return "ibus" in blob or "fcitx" in blob or "mozc" in blob
    return False


def ime_panel_visible(
    *,
    now: float | None = None,
    windows: list[WindowInfo] | None = None,
) -> bool:
    stamp = time.monotonic() if now is None else now
    if windows is None and stamp - float(_PANEL_CACHE["monotonic"]) < _CACHE_TTL_S:
        return bool(_PANEL_CACHE["visible"])
    rows = windows if windows is not None else _list_windows()
    visible = any(is_ime_panel_window(win) for win in rows)
    if windows is None:
        _PANEL_CACHE["monotonic"] = stamp
        _PANEL_CACHE["visible"] = visible
    return visible


def _list_windows() -> list[WindowInfo]:
    from ulauncher.modes.launcher.windows import cached_windows, list_windows, windows_cache_is_fresh

    if windows_cache_is_fresh():
        return cached_windows()
    return list_windows()
