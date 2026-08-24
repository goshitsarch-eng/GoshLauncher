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


def empty_popup_height(measured: float, fallback: int = 80) -> int:
    """goshos _emptyPopupHeight: entry preferred height, never the taller results list."""
    if measured > 0:
        return int(measured)
    return fallback


def gtk_window_owns_popup_width(desktop_id: str, is_x11_compatible: bool) -> bool:
    """GNOME Wayland is a fullscreen overlay; the card width is margin insets."""
    return desktop_id != "GNOME" or is_x11_compatible


def intersect_rect(first: dict[str, float], second: dict[str, float]) -> dict[str, int] | None:
    x = max(first["x"], second["x"])
    y = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    if right <= x or bottom <= y:
        return None
    return {"x": int(x), "y": int(y), "width": int(right - x), "height": int(bottom - y)}


def desktop_work_area_from_ewmh(values: Any, desktop_index: int = 0) -> dict[str, int] | None:
    """Parse _NET_WORKAREA (x, y, width, height per desktop)."""
    if values is None:
        return None
    if isinstance(values, dict):
        if "x" in values and "y" in values and "width" in values and "height" in values:
            return {key: int(values[key]) for key in ("x", "y", "width", "height")}
        return None
    try:
        items = list(values)
    except TypeError:
        return None
    if not items:
        return None
    if not isinstance(items[0], (int, float, str)):
        index = desktop_index if 0 <= desktop_index < len(items) else 0
        return desktop_work_area_from_ewmh(items[index], 0)
    nums: list[int] = []
    for item in items:
        try:
            nums.append(int(item))
        except (TypeError, ValueError):
            return None
    if len(nums) < 4:
        return None
    offset = max(0, int(desktop_index)) * 4
    if offset + 4 > len(nums):
        offset = 0
    return {"x": nums[offset], "y": nums[offset + 1], "width": nums[offset + 2], "height": nums[offset + 3]}


def work_area_for_monitor(geometry: dict[str, float], desktop_work_area: dict[str, float] | None) -> dict[str, int]:
    """goshos getWorkAreaForMonitor: keep panel struts out of the popup origin."""
    geo = {
        "x": int(geometry["x"]),
        "y": int(geometry["y"]),
        "width": int(geometry["width"]),
        "height": int(geometry["height"]),
    }
    if not desktop_work_area:
        return geo
    overlap = intersect_rect(geo, desktop_work_area)
    return overlap or geo


def work_area_from_hyprland_monitor(monitor: Any) -> dict[str, int] | None:
    # hyprctl -j monitors: reserved is [left, top, right, bottom]
    if not monitor:
        return None
    width = int(_get(monitor, "width", 0) or 0)
    height = int(_get(monitor, "height", 0) or 0)
    if width <= 0 or height <= 0:
        return None
    reserved = _get(monitor, "reserved", None) or [0, 0, 0, 0]
    try:
        left = int(reserved[0])
        top = int(reserved[1])
        right = int(reserved[2])
        bottom = int(reserved[3])
    except (TypeError, IndexError, ValueError):
        left = top = right = bottom = 0
    return {
        "x": int(_get(monitor, "x", 0) or 0) + left,
        "y": int(_get(monitor, "y", 0) or 0) + top,
        "width": max(0, width - left - right),
        "height": max(0, height - top - bottom),
    }


def hyprland_work_area_for_geometry(monitors: Any, geometry: dict[str, float]) -> dict[str, int] | None:
    rows = list(monitors or [])
    if not rows:
        return None
    match = None
    for monitor in rows:
        if int(_get(monitor, "x", 0) or 0) == int(geometry["x"]) and int(_get(monitor, "y", 0) or 0) == int(
            geometry["y"]
        ):
            match = monitor
            break
    if match is None:
        match = next((monitor for monitor in rows if _get(monitor, "focused", False)), rows[0])
    return work_area_from_hyprland_monitor(match)


def _ipc_rect(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        return {
            "x": int(value["x"]),
            "y": int(value["y"]),
            "width": int(value["width"]),
            "height": int(value["height"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _workspace_work_area(output: dict[str, Any]) -> dict[str, int] | None:
    """Visible i3/Sway workspace `rect` is the bar-free area on that output."""
    workspaces: list[dict[str, Any]] = []
    for child in output.get("nodes") or []:
        if not isinstance(child, dict):
            continue
        if str(child.get("type") or "") != "workspace":
            continue
        if str(child.get("name") or "").startswith("__"):
            continue
        workspaces.append(child)
    if not workspaces:
        return None
    chosen = next((ws for ws in workspaces if ws.get("focused")), None)
    if chosen is None:
        chosen = next((ws for ws in workspaces if ws.get("visible")), workspaces[0])
    return _ipc_rect(chosen.get("rect"))


def work_area_from_sway_tree(tree: Any, geometry: dict[str, float]) -> dict[str, int] | None:
    if not tree:
        return None
    gx = int(geometry["x"])
    gy = int(geometry["y"])

    def walk(node: Any) -> dict[str, int] | None:
        if not isinstance(node, dict):
            return None
        ntype = str(node.get("type") or "")
        name = str(node.get("name") or "")
        if ntype == "output" and not name.startswith("__"):
            rect = _ipc_rect(node.get("rect"))
            if rect and rect["x"] == gx and rect["y"] == gy:
                return _workspace_work_area(node)
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key) or []:
                found = walk(child)
                if found:
                    return found
        return None

    return walk(tree)


def resolve_monitor_work_area(
    geometry: dict[str, float],
    desktop_work_area: dict[str, float] | None = None,
    hyprland_monitors: Any = None,
    sway_tree: Any = None,
) -> dict[str, int]:
    hypr = hyprland_work_area_for_geometry(hyprland_monitors, geometry)
    if hypr:
        return hypr
    sway = work_area_from_sway_tree(sway_tree, geometry)
    if sway:
        return sway
    return work_area_for_monitor(geometry, desktop_work_area)


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
