from __future__ import annotations

import logging
from os.path import expanduser

from gi.repository import Gdk, Gtk

from ulauncher.gi import GLib
from ulauncher.ui import gtk4

logger = logging.getLogger(__name__)


def _icon_theme() -> Gtk.IconTheme | None:
    display = Gdk.Display.get_default()
    if not display:
        return None
    return Gtk.IconTheme.get_for_display(display)


def get_icon_path(icon: str, size: int = 32) -> str | None:
    try:
        if icon and isinstance(icon, str):
            icon = expanduser(icon)
            if icon.startswith("/"):
                return icon
            theme = _icon_theme()
            if not theme:
                return None
            paintable = theme.lookup_icon(icon, None, size, 1, Gtk.TextDirection.NONE, gtk4.icon_lookup_flags())
            if paintable:
                file = paintable.get_file()
                if file:
                    return file.get_path()

    except GLib.Error as err:
        logger.warning("Error '%s' occurred when trying to load icon path '%s'.", err, icon)
        logger.info("If this happens often, please see https://github.com/Ulauncher/Ulauncher/discussions/1346")

    return None
