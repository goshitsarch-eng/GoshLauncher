from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.click_outside import (
    backdrop_box,
    backdrop_claims_event,
    backdrop_pointer_action,
    backdrop_should_close,
    backdrop_teardown_order,
    click_is_outside_card,
    overlay_plan,
    overlay_skip_index,
    overlay_window_style,
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


def test_backdrop_teardown_order_hides_before_chrome_detach() -> None:
    order = backdrop_teardown_order()
    assert ",".join(order) == "disconnect,hide,remove-chrome,destroy"
    assert order.index("hide") < order.index("remove-chrome")


def test_overlay_plan_covers_each_monitor_and_can_skip_launcher_monitor() -> None:
    monitors = [
        SimpleNamespace(x=0, y=0, width=800, height=600),
        SimpleNamespace(x=800, y=0, width=640, height=480),
    ]
    plan = overlay_plan(monitors)
    assert [item["index"] for item in plan] == [0, 1]
    assert plan[0]["width"] == 800
    assert plan[1]["x"] == 800
    skipped = overlay_plan(monitors, skip_index=0)
    assert [item["index"] for item in skipped] == [1]
    assert overlay_skip_index(covers_current_monitor=True, current_index=0) == 0
    assert overlay_skip_index(covers_current_monitor=False, current_index=0) is None


def test_overlay_window_style_stays_unfocusable() -> None:
    style = overlay_window_style()
    assert style["decorated"] is False
    assert style["can_focus"] is False
    assert style["css_class"] == "goshos-backdrop"
    assert style["defer_close"] is True


def test_window_click_outside_closes_soon() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "ulauncher" / "ui" / "ulauncher_window.py").read_text()
    released = text.split("def on_backdrop_released", 1)[1].split("def ", 1)[0]
    assert "request_close(save_query=True)" in released
    assert "self.close(save_query=True)" not in released
