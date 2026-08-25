from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ulauncher import paths
from ulauncher.utils.lru_cache import lru_cache

if TYPE_CHECKING:
    from gi.repository import Gdk


logger = logging.getLogger(__name__)

DEFAULT_EXE_ICON = f"{paths.ASSETS}/icons/executable.png"


def _paintable_from_named_icon(icon: str, size: int, scale: int) -> Gdk.Paintable | None:
    from gi.repository import Gdk, Gtk

    from ulauncher.ui import gtk4

    display = Gdk.Display.get_default()
    if display is None:
        return None
    theme = Gtk.IconTheme.get_for_display(display)
    if theme is None:
        return None
    return theme.lookup_icon(icon, None, size, scale, Gtk.TextDirection.NONE, gtk4.icon_lookup_flags())


def _paintable_from_file(path: str, size: int, scale: int) -> Gdk.Paintable:
    from gi.repository import Gdk, GdkPixbuf, Gio, Gtk

    from ulauncher.gi import GLib

    gfile = Gio.File.new_for_path(path)
    if path.lower().endswith(".svg"):
        return Gtk.IconPaintable.new_for_file(gfile, size, scale)
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
    except GLib.Error:
        return Gtk.IconPaintable.new_for_file(gfile, size, scale)
    if not pixbuf:
        return Gtk.IconPaintable.new_for_file(gfile, size, scale)
    return Gdk.Texture.new_for_pixbuf(pixbuf)


@lru_cache(maxsize=50)
def load_icon_paintable(icon: str, size: int, scaling_factor: int = 1) -> Gdk.Paintable:
    from ulauncher.gi import GLib

    real_size = size * scaling_factor
    try:
        if icon.startswith("/"):
            return _paintable_from_file(icon, real_size, scaling_factor)
        named = _paintable_from_named_icon(icon, real_size, scaling_factor)
        if named is not None:
            return named
        from ulauncher.ui.get_icon_path import get_icon_path

        path = get_icon_path(icon, real_size) or DEFAULT_EXE_ICON
        return _paintable_from_file(path, real_size, scaling_factor)
    except GLib.Error as e:
        if icon == DEFAULT_EXE_ICON:
            msg = f"Could not load fallback icon: {icon}"
            raise RuntimeError(msg) from e
        logger.warning("Could not load specified icon %s (%s). Will use fallback icon", icon, e)
        return load_icon_paintable(DEFAULT_EXE_ICON, size, scaling_factor)


# GTK3 name kept so call sites that still say "surface" get a paintable on GTK4.
load_icon_surface = load_icon_paintable
