from __future__ import annotations

from ulauncher.modes.launcher.click_outside import backdrop_teardown_order
from ulauncher.ui.backdrop_overlay import PopupBackdrop


def test_popup_backdrop_show_and_destroy_are_idempotent() -> None:
    closed: list[bool] = []
    overlay = PopupBackdrop(lambda: closed.append(True))
    overlay.show()
    assert overlay.window_count() >= 1
    overlay.destroy()
    assert overlay.window_count() == 0
    overlay.destroy()
    assert overlay.window_count() == 0
    assert ",".join(backdrop_teardown_order()) == "disconnect,hide,remove-chrome,destroy"


def test_popup_backdrop_set_layer_accepts_top_and_overlay() -> None:
    overlay = PopupBackdrop(lambda: None)
    overlay.show()
    overlay.set_layer("top")
    overlay.set_layer("overlay")
    overlay.set_layer("not-a-layer")
    overlay.destroy()
    assert overlay.window_count() == 0
