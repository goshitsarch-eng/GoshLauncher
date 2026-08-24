from __future__ import annotations

import logging

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
                if surface is not None and callable(get_at):
                    if monitor := get_at(surface):
                        return monitor
            position = getattr(pointer, "get_position", None)
            if callable(position):
                coords = position()
                # GTK4 may return (surface, x, y) or (x, y)
                if len(coords) >= 2:
                    x, y = int(coords[-2]), int(coords[-1])
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


def get_text_scaling_factor() -> float:
    return Gio.Settings.new("org.gnome.desktop.interface").get_double("text-scaling-factor")
