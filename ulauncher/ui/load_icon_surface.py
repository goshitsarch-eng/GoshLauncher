from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ulauncher import paths
from ulauncher.utils.lru_cache import lru_cache

if TYPE_CHECKING:
    from gi.repository import Gdk


logger = logging.getLogger(__name__)

DEFAULT_EXE_ICON = f"{paths.ASSETS}/icons/executable.png"


@lru_cache(maxsize=50)
def load_icon_paintable(icon: str, size: int, scaling_factor: int = 1) -> Gdk.Paintable:
    from gi.repository import Gdk, GdkPixbuf

    from ulauncher.gi import GLib

    real_size = size * scaling_factor
    try:
        if not icon.startswith("/"):
            from ulauncher.ui.get_icon_path import get_icon_path

            icon = get_icon_path(icon, real_size) or DEFAULT_EXE_ICON
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon, real_size, real_size)
        if not pixbuf:
            msg = f"Could not load icon pixbuf: {icon}"
            raise RuntimeError(msg)
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        return texture
    except GLib.Error as e:
        if icon == DEFAULT_EXE_ICON:
            msg = f"Could not load fallback icon: {icon}"
            raise RuntimeError(msg) from e

        logger.warning("Could not load specified icon %s (%s). Will use fallback icon", icon, e)
        return load_icon_paintable(DEFAULT_EXE_ICON, size, scaling_factor)


# GTK3 name kept so call sites that still say "surface" get a paintable on GTK4.
load_icon_surface = load_icon_paintable
