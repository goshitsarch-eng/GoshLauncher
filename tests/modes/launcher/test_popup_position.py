from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.popup_position import (
    MIN_RESULTS_HEIGHT,
    keyboard_overlap_from_box,
    lift_origin_for_results,
    place_popup,
    popup_origin,
    popup_width_for_work_area,
    results_max_height_for_work_area,
    work_area_avoiding_keyboard,
)
from ulauncher.modes.launcher.ui_scale import (
    css_px,
    next_scale_listen_action,
    stage_px,
    theme_scale,
    theme_scale_from_context,
)


def test_theme_scale_and_stage_css_px() -> None:
    assert theme_scale(2) == 2
    assert theme_scale(0) == 1
    assert theme_scale(-1) == 1
    assert theme_scale_from_context(None) == 1
    assert theme_scale_from_context({"scale_factor": 2}) == 2
    assert theme_scale_from_context(SimpleNamespace(scale_factor=0)) == 1
    assert next_scale_listen_action(True, {"scale_factor": 2}) == "keep"
    assert next_scale_listen_action(False, None) == "wait"
    assert next_scale_listen_action(False, {"scale_factor": 2}) == "listen"
    assert stage_px(600, 2) == 1200
    assert css_px(800, 2) == 400


def test_popup_origin_and_width_match_goshos() -> None:
    work = {"x": 100, "y": 40, "width": 1800, "height": 1000}
    assert popup_origin(work, 600, 80, "center")["x"] == 700
    assert popup_origin(work, 600, 80, "center")["y"] == 500
    assert popup_origin(work, 600, 80, "top")["y"] == 160
    tiny = {"x": 0, "y": 0, "width": 400, "height": 300}
    assert popup_origin(tiny, 600, 80, "center")["x"] == 0
    assert popup_origin(tiny, 200, 400, "center")["y"] == 0
    assert popup_origin({"x": 50, "y": 20, "width": 400, "height": 300}, 600, 80, "center")["x"] == 50
    assert popup_width_for_work_area(600, 1920) == 600
    assert popup_width_for_work_area(1200, 800) == 800
    assert popup_width_for_work_area(600, 0) == 600
    assert popup_width_for_work_area(600, 1920, 2) == 1200
    assert popup_width_for_work_area(1200, 800, 2) == 800
    assert results_max_height_for_work_area(400, 900) == 400
    assert results_max_height_for_work_area(800, 220) == 220
    assert results_max_height_for_work_area(400, 0) == 0
    assert results_max_height_for_work_area(400, -20) == 0


def test_place_popup_lifts_short_top_and_keeps_hidpi_css() -> None:
    work = {"x": 100, "y": 40, "width": 1800, "height": 1000}
    short_top = {"x": 0, "y": 0, "width": 800, "height": 200}
    raw_top = popup_origin(short_top, 600, 80, "top")
    lifted_top = lift_origin_for_results(raw_top, short_top, 80, MIN_RESULTS_HEIGHT)
    assert lifted_top["y"] < raw_top["y"]
    placed_short = place_popup(short_top, 600, 80, "top", 800)
    assert placed_short["results_max"] >= MIN_RESULTS_HEIGHT
    placed_tall = place_popup(work, 600, 80, "center", 400)
    assert placed_tall["y"] == popup_origin(work, 600, 80, "center")["y"]
    assert placed_tall["results_max"] == 400
    packed = {"x": 0, "y": 0, "width": 400, "height": 80}
    assert place_popup(packed, 200, 80, "center", 400)["results_max"] == 0
    hidpi_work = {"x": 0, "y": 0, "width": 3840, "height": 2160}
    placed_hi = place_popup(hidpi_work, 1200, 112, "center", 400, None, 2)
    assert placed_hi["results_max"] == 400
    hidpi_short = {"x": 0, "y": 0, "width": 1920, "height": 400}
    placed_hi_short = place_popup(hidpi_short, 1200, 112, "top", 800, None, 2)
    assert placed_hi_short["results_max"] <= 120
    assert place_popup(hidpi_short, 600, 112, "top", 800)["results_max"] == 240


def test_work_area_avoids_keyboard_on_same_monitor() -> None:
    work = {"x": 100, "y": 40, "width": 1800, "height": 1000}
    kb_hidden = keyboard_overlap_from_box({"visible": True, "y": 1080, "height": 300, "translation_y": 0}, 0, 0)
    assert work_area_avoiding_keyboard(work, kb_hidden) == work
    kb_open = keyboard_overlap_from_box({"visible": True, "y": 1080, "height": 300, "translation_y": -300}, 0, 0)
    assert work_area_avoiding_keyboard({"x": 0, "y": 0, "width": 1920, "height": 1080}, kb_open)["height"] == 780
    kb_child = keyboard_overlap_from_box(
        {"visible": True, "y": 1080, "height": 300, "translation_y": 0},
        0,
        0,
        {"height": 300, "translation_y": -300},
    )
    assert work_area_avoiding_keyboard({"x": 0, "y": 0, "width": 1920, "height": 1080}, kb_child)["height"] == 780
    kb_other = keyboard_overlap_from_box({"visible": True, "y": 1080, "height": 300, "translation_y": -300}, 1, 0)
    assert work_area_avoiding_keyboard({"x": 0, "y": 0, "width": 1920, "height": 1080}, kb_other)["height"] == 1080
    assert keyboard_overlap_from_box(None, 0, 0)["visible"] is False
    hidden = {
        "visible": False,
        "y": 800,
        "height": 300,
        "translationY": -300,
        "monitorIndex": 0,
        "workMonitorIndex": 0,
    }
    assert work_area_avoiding_keyboard(work, hidden) == work
