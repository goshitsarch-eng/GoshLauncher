from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.popup_position import (
    MIN_RESULTS_HEIGHT,
    desktop_work_area_from_ewmh,
    empty_popup_height,
    gtk_window_owns_popup_width,
    keyboard_overlap_from_box,
    lift_origin_for_results,
    offset_from_origin,
    place_popup,
    popup_origin,
    popup_width_for_work_area,
    resolve_monitor_work_area,
    results_max_height_for_work_area,
    work_area_avoiding_keyboard,
    work_area_for_monitor,
    work_area_from_hyprland_monitor,
    work_area_from_sway_tree,
)
from ulauncher.modes.launcher.ui_scale import (
    css_px,
    gtk_layout_scale,
    layout_scale_for_toolkit,
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


def test_gtk_layout_scale_does_not_double_hidpi() -> None:
    assert gtk_layout_scale() == 1
    assert gtk_layout_scale(2) == 1
    assert layout_scale_for_toolkit("st", 2) == 2
    assert layout_scale_for_toolkit("gtk", 2) == 1
    assert popup_width_for_work_area(600, 1920, 2) == 1200
    assert popup_width_for_work_area(600, 1920, gtk_layout_scale(2)) == 600
    work = {"x": 0, "y": 0, "width": 1920, "height": 1080}
    placed_gtk = place_popup(work, 600, 80, "center", 400, None, gtk_layout_scale(2))
    assert placed_gtk["x"] == popup_origin(work, 600, 80, "center")["x"]
    assert placed_gtk["results_max"] == 400


def test_empty_popup_height_uses_measured_entry() -> None:
    assert empty_popup_height(0) == 80
    assert empty_popup_height(-4) == 80
    assert empty_popup_height(112) == 112
    assert gtk_window_owns_popup_width("GNOME", False) is False
    assert gtk_window_owns_popup_width("GNOME", True) is True
    assert gtk_window_owns_popup_width("KDE", False) is True


def test_work_area_sits_below_panel_struts() -> None:
    geometry = {"x": 0, "y": 0, "width": 1920, "height": 1080}
    assert desktop_work_area_from_ewmh(None) is None
    assert desktop_work_area_from_ewmh([0, 32, 1920, 1048]) == {"x": 0, "y": 32, "width": 1920, "height": 1048}
    assert desktop_work_area_from_ewmh([0, 0, 1920, 1080, 0, 40, 1920, 1040], 1) == {
        "x": 0,
        "y": 40,
        "width": 1920,
        "height": 1040,
    }
    assert desktop_work_area_from_ewmh([[0, 24, 1920, 1056]]) == {"x": 0, "y": 24, "width": 1920, "height": 1056}
    below_panel = work_area_for_monitor(geometry, {"x": 0, "y": 32, "width": 1920, "height": 1048})
    assert below_panel == {"x": 0, "y": 32, "width": 1920, "height": 1048}
    assert work_area_for_monitor(geometry, None) == geometry
    assert work_area_for_monitor(geometry, {"x": 2000, "y": 0, "width": 100, "height": 100}) == geometry
    origin = popup_origin(below_panel, 600, 80, "top")
    assert origin["y"] == int(32 + 1048 * 0.12)
    hypr = work_area_from_hyprland_monitor({"x": 0, "y": 0, "width": 1920, "height": 1080, "reserved": [0, 40, 0, 48]})
    assert hypr == {"x": 0, "y": 40, "width": 1920, "height": 992}
    resolved = resolve_monitor_work_area(
        geometry,
        {"x": 0, "y": 32, "width": 1920, "height": 1048},
        [{"x": 0, "y": 0, "width": 1920, "height": 1080, "reserved": [0, 40, 0, 0], "focused": True}],
    )
    assert resolved["y"] == 40


def test_work_area_from_sway_workspace_rect() -> None:
    geometry = {"x": 0, "y": 0, "width": 1920, "height": 1080}
    tree = {
        "type": "root",
        "nodes": [
            {"type": "output", "name": "__i3", "rect": {"x": 0, "y": 0, "width": 0, "height": 0}, "nodes": []},
            {
                "type": "output",
                "name": "eDP-1",
                "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                "nodes": [
                    {
                        "type": "workspace",
                        "name": "__i3_scratch",
                        "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                    },
                    {
                        "type": "workspace",
                        "name": "1",
                        "visible": True,
                        "rect": {"x": 0, "y": 32, "width": 1920, "height": 1048},
                    },
                    {
                        "type": "workspace",
                        "name": "2",
                        "focused": True,
                        "rect": {"x": 0, "y": 40, "width": 1920, "height": 1040},
                    },
                ],
            },
        ],
    }
    assert work_area_from_sway_tree(tree, geometry) == {"x": 0, "y": 40, "width": 1920, "height": 1040}
    origin = popup_origin(work_area_from_sway_tree(tree, geometry) or geometry, 600, 80, "top")
    assert origin["y"] == int(40 + 1040 * 0.12)
    resolved = resolve_monitor_work_area(geometry, {"x": 0, "y": 8, "width": 1920, "height": 1072}, None, tree)
    assert resolved["y"] == 40
    other = {"x": 1920, "y": 0, "width": 1920, "height": 1080}
    assert work_area_from_sway_tree(tree, other) is None
    assert work_area_from_sway_tree(None, geometry) is None
    visible_only = {
        "type": "root",
        "nodes": [
            {
                "type": "output",
                "name": "eDP-1",
                "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                "nodes": [
                    {
                        "type": "workspace",
                        "name": "1",
                        "visible": True,
                        "rect": {"x": 0, "y": 32, "width": 1920, "height": 1048},
                    }
                ],
            }
        ],
    }
    assert work_area_from_sway_tree(visible_only, geometry) == {"x": 0, "y": 32, "width": 1920, "height": 1048}


def test_layer_shell_offset_keeps_panel_inset() -> None:
    work = {"x": 0, "y": 32, "width": 1920, "height": 1048}
    placed = place_popup(work, 600, 80, "top", 400)
    overlay = offset_from_origin(placed, work)
    output = offset_from_origin(placed, {"x": 0, "y": 0})
    assert overlay["y"] == int(placed["y"] - 32)
    assert output["y"] == int(placed["y"])
    assert output["y"] - overlay["y"] == 32
    assert output["x"] == int(placed["x"])
