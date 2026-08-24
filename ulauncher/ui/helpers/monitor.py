from __future__ import annotations

import logging
from typing import Any

from gi.repository import Gdk, GdkX11  # type: ignore[missing-module-attribute]

from ulauncher.gi import Gio

logger = logging.getLogger(__name__)


def _monitors(display: Gdk.Display) -> list[Gdk.Monitor]:
    model = display.get_monitors()
    return [model.get_item(i) for i in range(model.get_n_items())]


def get_monitor(use_mouse_position: bool = False) -> Gdk.Monitor | None:
    display = Gdk.Display.get_default()
    if not display:
        logger.warning("Could not get default display")
        return None

    monitors = _monitors(display)
    if not monitors:
        return None

    if use_mouse_position:
        if (
            isinstance(display, GdkX11.X11Display)
            and (seat := display.get_default_seat())
            and (pointer := seat.get_pointer())
        ):
            surface_at = getattr(pointer, "get_surface_at_position", None)
            if callable(surface_at):
                located = surface_at()
                surface = located[0] if located else None
                get_at = getattr(display, "get_monitor_at_surface", None)
                if surface is not None and callable(get_at) and (monitor := get_at(surface)):
                    return monitor
            position = getattr(pointer, "get_position", None)
            if callable(position):
                coords = position()
                # GTK4 may return (surface, x, y) or (x, y)
                try:
                    x, y = int(coords[-2]), int(coords[-1])
                except (TypeError, ValueError, IndexError):
                    x = y = None
                if x is not None and y is not None:
                    for monitor in monitors:
                        geo = monitor.get_geometry()
                        if geo.x <= x < geo.x + geo.width and geo.y <= y < geo.y + geo.height:
                            return monitor
        logger.debug("Could not get mouse position. Defaulting to first monitor")

    return monitors[0]


def get_monitor_geometries() -> list[Gdk.Rectangle]:
    display = Gdk.Display.get_default()
    if not display:
        logger.warning("Could not get default display")
        return []
    return [monitor.get_geometry() for monitor in _monitors(display)]


def get_ewmh_desktop_work_area() -> dict[str, int] | None:
    try:
        from ulauncher.modes.launcher.popup_position import desktop_work_area_from_ewmh
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
        raw = ewmh.getWorkArea()
        desktop = 0
        current = ewmh.getCurrentDesktop()
        if current is not None:
            desktop = int(current)
        return desktop_work_area_from_ewmh(raw, desktop)
    except Exception:
        logger.debug("EWMH work area unavailable", exc_info=True)
        return None


def get_hyprland_monitors() -> list[Any] | None:
    import json
    import subprocess

    from ulauncher.modes.launcher.unredirect import hyprland_session_active

    if not hyprland_session_active():
        return None
    try:
        payload = subprocess.check_output(["hyprctl", "-j", "monitors"], timeout=1)
        data = json.loads(payload)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, TypeError):
        logger.debug("Hyprland monitors unavailable", exc_info=True)
        return None
    return data if isinstance(data, list) else None


def monitor_work_geometry(monitor: Gdk.Monitor) -> Gdk.Rectangle:
    """Monitor geometry minus panel struts (EWMH _NET_WORKAREA or Hyprland reserved)."""
    from ulauncher.modes.launcher.popup_position import resolve_monitor_work_area

    geo = monitor.get_geometry()
    work = resolve_monitor_work_area(
        {"x": geo.x, "y": geo.y, "width": geo.width, "height": geo.height},
        get_ewmh_desktop_work_area(),
        get_hyprland_monitors(),
    )
    rect = Gdk.Rectangle()
    rect.x = int(work["x"])
    rect.y = int(work["y"])
    rect.width = int(work["width"])
    rect.height = int(work["height"])
    return rect


def get_text_scaling_factor() -> float:
    return Gio.Settings.new("org.gnome.desktop.interface").get_double("text-scaling-factor")
