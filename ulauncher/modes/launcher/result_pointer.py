"""Result-row pointer and touch claiming, ported from Spotlight-goshos resultPointer.js."""

from __future__ import annotations

from typing import Any

PRIMARY_BUTTON = 1
TOUCH_TAP_SLOP = 16


def row_pointer_action(phase: str, button: int, was_pressed: bool) -> dict[str, Any]:
    if phase == "leave":
        return {"pressed": False, "action": "propagate"}
    if phase == "hold":
        return {"pressed": was_pressed, "action": "stop" if was_pressed else "propagate"}
    if button != PRIMARY_BUTTON:
        return {"pressed": was_pressed, "action": "propagate"}
    if phase == "press":
        return {"pressed": True, "action": "stop"}
    if phase == "release" and was_pressed:
        return {"pressed": False, "action": "activate"}
    return {"pressed": False, "action": "propagate"}


def should_apply_hover_selection(painting: bool, now: float, suppressed_until: float) -> bool:
    return (not painting) and now >= suppressed_until


def row_touch_phase(kind: str) -> str | None:
    if kind == "touch-begin":
        return "press"
    if kind == "touch-end":
        return "release"
    if kind == "touch-cancel":
        return "leave"
    if kind == "touch-update":
        return "hold"
    return None


def event_coord_y(coords: Any) -> float | None:
    if not isinstance(coords, (list, tuple)):
        return None
    if len(coords) > 2 and isinstance(coords[2], (int, float)):
        return float(coords[2])
    if len(coords) > 1 and isinstance(coords[1], (int, float)):
        return float(coords[1])
    return None


def touch_moved_past_slop(start_y: Any, y: Any, slop: int | None = None) -> bool:
    if not isinstance(start_y, (int, float)) or not isinstance(y, (int, float)):
        return False
    limit = TOUCH_TAP_SLOP if slop is None else slop
    return abs(y - start_y) > limit


def should_ignore_pointer_for_touch(is_touchscreen: bool) -> bool:
    return bool(is_touchscreen)


def row_touch_gesture_action(kind: str, pressed: bool, dragged: bool) -> dict[str, Any]:
    if kind == "touch-begin":
        return {"pressed": True, "dragged": False, "action": "propagate"}
    if kind == "touch-cancel":
        return {"pressed": False, "dragged": False, "action": "propagate"}
    if kind == "touch-update":
        return {"pressed": pressed, "dragged": dragged, "action": "propagate"}
    if kind == "touch-end" and pressed and not dragged:
        return {"pressed": False, "dragged": False, "action": "activate"}
    return {"pressed": False, "dragged": False, "action": "propagate"}


def touch_kind_from_event_type(event_type: object) -> str | None:
    raw = getattr(event_type, "value_nick", None) or getattr(event_type, "name", None) or event_type
    nick = str(raw).rsplit(".", 1)[-1].lower().replace("_", "-")
    if nick.startswith("gdk-"):
        nick = nick[4:]
    if nick in {"touch-begin", "touch-update", "touch-end", "touch-cancel"}:
        return nick
    return None


def event_y(event: Any) -> float | None:
    for name in ("get_position", "get_coords"):
        getter = getattr(event, name, None)
        if not callable(getter):
            continue
        y = event_coord_y(getter())
        if y is not None:
            return y
    return None


def device_is_touchscreen(source: object) -> bool:
    nick = str(getattr(source, "value_nick", None) or getattr(source, "name", None) or source).lower()
    return "touchscreen" in nick.replace("_", "-")


def next_row_touch_state(
    kind: str,
    y: float | None,
    start_y: Any,
    pressed: bool,
    dragged: bool,
) -> dict[str, Any]:
    next_start = start_y
    next_dragged = dragged
    if kind == "touch-begin":
        next_start = y
        next_dragged = False
    elif kind == "touch-update" and touch_moved_past_slop(start_y, y):
        next_dragged = True
    action = row_touch_gesture_action(kind, pressed, next_dragged)
    return {"start_y": next_start, **action}
