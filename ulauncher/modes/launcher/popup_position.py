"""Work-area origin for the popup, from spotlight-goshos popupPosition.js."""

from __future__ import annotations

from typing import Any

from ulauncher.modes.launcher.ui_scale import css_px, stage_px, theme_scale

MIN_RESULTS_HEIGHT = 120


def _get(obj: Any, name: str, default: Any = 0) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def popup_width_for_work_area(requested: float, work_width: float, scale: Any = None) -> int:
    width = stage_px(requested, scale)
    if work_width > 0 and width > work_width:
        return int(work_width)
    return width


def results_max_height_for_work_area(requested: float, space_below: float) -> float:
    if space_below <= 0:
        return 0
    return min(requested, space_below)


def space_below_origin(work_area: dict[str, float], origin_y: float, empty_height: float) -> float:
    return work_area["y"] + work_area["height"] - origin_y - empty_height


def lift_origin_for_results(
    origin: dict[str, float],
    work_area: dict[str, float],
    empty_height: float,
    min_results: float,
) -> dict[str, float]:
    if min_results <= 0:
        return origin
    space = space_below_origin(work_area, origin["y"], empty_height)
    if space >= min_results:
        return origin
    needed = empty_height + min_results
    y = work_area["y"] + work_area["height"] - needed
    max_y = work_area["y"] + work_area["height"] - empty_height
    y = min(y, max_y)
    y = max(y, work_area["y"])
    return {"x": origin["x"], "y": y}


def popup_origin(
    work_area: dict[str, float],
    popup_width: float,
    popup_height: float,
    position: str,
) -> dict[str, float]:
    x = int(work_area["x"] + (work_area["width"] - popup_width) / 2)
    if position == "top":
        y = int(work_area["y"] + work_area["height"] * 0.12)
    else:
        y = int(work_area["y"] + (work_area["height"] - popup_height) / 2)

    max_x = work_area["x"] + work_area["width"] - popup_width
    max_y = work_area["y"] + work_area["height"] - popup_height
    if x > max_x:
        x = int(max_x)
    if x < work_area["x"]:
        x = int(work_area["x"])
    if y > max_y:
        y = int(max_y)
    if y < work_area["y"]:
        y = int(work_area["y"])
    return {"x": x, "y": y}


def place_popup(
    work_area: dict[str, float],
    popup_width: float,
    empty_height: float,
    position: str,
    requested_results: float,
    min_results: float | None = None,
    scale: Any = None,
) -> dict[str, float]:
    factor = theme_scale(scale)
    floor_logical = MIN_RESULTS_HEIGHT if min_results is None else min_results
    floor = stage_px(floor_logical, factor)
    requested = stage_px(requested_results, factor)
    origin = popup_origin(work_area, popup_width, empty_height, position)
    origin = lift_origin_for_results(origin, work_area, empty_height, min(requested, floor))
    return {
        "x": origin["x"],
        "y": origin["y"],
        "results_max": css_px(
            results_max_height_for_work_area(
                requested,
                space_below_origin(work_area, origin["y"], empty_height),
            ),
            factor,
        ),
    }


def keyboard_overlap_from_box(
    box: Any,
    keyboard_monitor_index: int,
    work_monitor_index: int,
    slide: Any = None,
) -> dict[str, Any]:
    if not box:
        return {
            "visible": False,
            "y": 0,
            "height": 0,
            "translationY": 0,
            "monitorIndex": -1,
            "workMonitorIndex": work_monitor_index,
        }
    mover = slide or box
    slide_height = _get(slide, "height", 0) if slide else 0
    height = slide_height if slide and slide_height > 0 else _get(box, "height", 0)
    return {
        "visible": bool(_get(box, "visible", False)),
        "y": _get(box, "y", 0),
        "height": height,
        "translationY": _get(mover, "translation_y", 0),
        "monitorIndex": keyboard_monitor_index,
        "workMonitorIndex": work_monitor_index,
    }


def work_area_avoiding_keyboard(work_area: dict[str, float], keyboard: Any) -> dict[str, float]:
    if not keyboard or not _get(keyboard, "visible", False) or _get(keyboard, "height", 0) <= 0:
        return work_area
    monitor_index = _get(keyboard, "monitorIndex", -1)
    work_monitor_index = _get(keyboard, "workMonitorIndex", -1)
    if monitor_index >= 0 and work_monitor_index >= 0 and monitor_index != work_monitor_index:
        return work_area
    top = _get(keyboard, "y", 0) + _get(keyboard, "translationY", 0)
    work_bottom = work_area["y"] + work_area["height"]
    if top >= work_bottom:
        return work_area
    if top + _get(keyboard, "height", 0) <= work_area["y"]:
        return work_area
    if top <= work_area["y"]:
        return {"x": work_area["x"], "y": work_area["y"], "width": work_area["width"], "height": 0}
    return {
        "x": work_area["x"],
        "y": work_area["y"],
        "width": work_area["width"],
        "height": top - work_area["y"],
    }
