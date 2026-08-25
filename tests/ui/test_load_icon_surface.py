from __future__ import annotations

import logging

import pytest

from tests.ui.conftest import GTK4_AVAILABLE

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")

if GTK4_AVAILABLE:
    from tests.ui.look_paint import display_available


def test_gear_svg_loads_as_icon_paintable(caplog: pytest.LogCaptureFixture) -> None:
    from gi.repository import Gtk

    from ulauncher import paths
    from ulauncher.ui.load_icon_surface import DEFAULT_EXE_ICON, load_icon_paintable

    if not display_available():
        pytest.skip("no Gdk display")

    gear = f"{paths.ASSETS}/icons/gear.svg"
    with caplog.at_level(logging.WARNING, logger="ulauncher.ui.load_icon_surface"):
        paintable = load_icon_paintable(gear, 16, 1)
    assert isinstance(paintable, Gtk.IconPaintable)
    icon_file = paintable.get_file()
    assert icon_file is not None
    assert (icon_file.get_path() or "").endswith("gear.svg")
    assert "Will use fallback icon" not in caplog.text
    named = load_icon_paintable("emblem-system-symbolic", 16, 1)
    assert isinstance(named, Gtk.IconPaintable)
    fallback = load_icon_paintable(DEFAULT_EXE_ICON, 16, 1)
    assert fallback is not paintable
