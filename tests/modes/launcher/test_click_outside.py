from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.click_outside import (
    backdrop_box,
    backdrop_claims_event,
    backdrop_pointer_action,
    backdrop_should_close,
    click_is_outside_card,
)


def test_backdrop_pointer_action_claims_press_and_closes_on_release() -> None:
    assert backdrop_pointer_action("button-press") == "stop"
    assert backdrop_pointer_action("touch-begin") == "stop"
    assert backdrop_pointer_action("button-release") == "close"
    assert backdrop_pointer_action("touch-end") == "close"
    assert backdrop_pointer_action("motion") == "propagate"
    assert backdrop_claims_event("button-press") is True
    assert backdrop_should_close("button-release") is True
    assert backdrop_should_close("button-press") is False


def test_click_is_outside_card() -> None:
    assert click_is_outside_card(-1, 10, 100, 80) is True
    assert click_is_outside_card(10, 10, 100, 80) is False
    assert click_is_outside_card(101, 10, 100, 80) is True


def test_backdrop_box_unions_monitors() -> None:
    monitors = [
        SimpleNamespace(x=0, y=0, width=800, height=600),
        SimpleNamespace(x=800, y=0, width=640, height=480),
    ]
    box = backdrop_box(monitors)
    assert box == {"x": 0, "y": 0, "width": 1440, "height": 600}
