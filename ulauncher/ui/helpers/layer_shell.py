# pyrefly: ignore-errors
"""Wayland layer-shell positioning for the GTK4 launcher window."""

from __future__ import annotations

import gi
from gi.repository import Gtk

from ulauncher.gi import GLib

LayerShell = None
try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell  # type: ignore[attr-defined]
except (ValueError, ImportError):
    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell as LayerShell  # type: ignore[attr-defined]
    except (ValueError, ImportError):
        LayerShell = None


def is_supported() -> bool:
    try:
        return LayerShell is not None and LayerShell.is_supported()
    except (GLib.Error, AttributeError, TypeError):
        return False


def enable(window: Gtk.Window) -> bool:
    if not is_supported():
        return False

    LayerShell.init_for_window(window)
    LayerShell.set_namespace(window, "ulauncher")
    keyboard_mode = getattr(LayerShell, "KeyboardMode", None)
    if keyboard_mode is not None:
        LayerShell.set_keyboard_mode(window, keyboard_mode.EXCLUSIVE)
    LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
    LayerShell.set_exclusive_zone(window, 0)
    return True


def set_vertical_position(window: Gtk.Window, pos_y: float) -> None:
    LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
    LayerShell.set_margin(window, LayerShell.Edge.TOP, int(pos_y))


def enable_input_only(window: Gtk.Window, monitor: object | None = None) -> bool:
    """Fullscreen overlay that must not steal keyboard focus from the launcher."""
    if not is_supported():
        return False

    LayerShell.init_for_window(window)
    LayerShell.set_namespace(window, "ulauncher-backdrop")
    keyboard_mode = getattr(LayerShell, "KeyboardMode", None)
    if keyboard_mode is not None:
        none_mode = getattr(keyboard_mode, "NONE", None)
        if none_mode is not None:
            LayerShell.set_keyboard_mode(window, none_mode)
    LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
    LayerShell.set_exclusive_zone(window, 0)
    edge = getattr(LayerShell, "Edge", None)
    if edge is not None:
        for name in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            side = getattr(edge, name, None)
            if side is not None:
                LayerShell.set_anchor(window, side, True)
    if monitor is not None:
        set_monitor = getattr(LayerShell, "set_monitor", None)
        if callable(set_monitor):
            set_monitor(window, monitor)
    return True
