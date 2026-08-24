from __future__ import annotations

from ulauncher.modes.launcher.result_pointer import (
    PRIMARY_BUTTON,
    TOUCH_TAP_SLOP,
    event_coord_y,
    row_pointer_action,
    row_touch_gesture_action,
    row_touch_phase,
    should_apply_hover_selection,
    should_ignore_pointer_for_touch,
    touch_moved_past_slop,
)


def test_row_pointer_action_claims_primary_press() -> None:
    assert row_pointer_action("press", PRIMARY_BUTTON, False)["action"] == "stop"
    assert row_pointer_action("release", PRIMARY_BUTTON, True)["action"] == "activate"
    assert row_pointer_action("release", PRIMARY_BUTTON, False)["action"] == "propagate"
    assert row_pointer_action("leave", PRIMARY_BUTTON, True)["pressed"] is False
    assert row_pointer_action("press", 3, False)["action"] == "propagate"
    assert row_pointer_action("hold", PRIMARY_BUTTON, True)["action"] == "stop"
    assert row_pointer_action("release", PRIMARY_BUTTON, True)["action"] == "activate"


def test_hover_selection_gates() -> None:
    assert should_apply_hover_selection(True, 10, 0) is False
    assert should_apply_hover_selection(False, 10, 0) is True
    assert should_apply_hover_selection(False, 10, 20) is False


def test_touch_mapping_and_slop() -> None:
    assert row_touch_phase("touch-begin") == "press"
    assert row_touch_phase("touch-end") == "release"
    assert row_touch_phase("touch-cancel") == "leave"
    assert row_touch_phase("touch-update") == "hold"
    assert event_coord_y([0, 12]) == 12
    assert event_coord_y([0, 1, 9]) == 9
    assert event_coord_y("nope") is None
    assert touch_moved_past_slop(0, TOUCH_TAP_SLOP + 1) is True
    assert touch_moved_past_slop(0, TOUCH_TAP_SLOP) is False
    assert should_ignore_pointer_for_touch(True) is True
    assert row_touch_gesture_action("touch-end", True, False)["action"] == "activate"
    assert row_touch_gesture_action("touch-end", True, True)["action"] == "propagate"
