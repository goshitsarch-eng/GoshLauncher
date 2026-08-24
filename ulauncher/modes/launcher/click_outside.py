"""Click-outside claiming, ported from Spotlight-goshos backdropBox.js."""

from __future__ import annotations

from typing import Any

# swallow the press so click-outside does not activate a window below
_STOP_KINDS = frozenset({"button-press", "touch-begin", "touch-update", "touch-cancel"})
_CLOSE_KINDS = frozenset({"button-release", "touch-end"})


def backdrop_pointer_action(kind: str) -> str:
    if kind in _STOP_KINDS:
        return "stop"
    if kind in _CLOSE_KINDS:
        return "close"
    return "propagate"


def backdrop_claims_event(kind: str) -> bool:
    return backdrop_pointer_action(kind) != "propagate"


def backdrop_should_close(kind: str) -> bool:
    return backdrop_pointer_action(kind) == "close"


def click_is_outside_card(x: float, y: float, width: float, height: float) -> bool:
    return x < 0 or y < 0 or x > width or y > height


def backdrop_teardown_order() -> list[str]:
    # clutter 18 aborts if a mapped actor is detached
    return ["disconnect", "hide", "remove-chrome", "destroy"]


def backdrop_box(monitors: list[Any]) -> dict[str, float]:
    if not monitors:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    min_x = float(getattr(monitors[0], "x", 0))
    min_y = float(getattr(monitors[0], "y", 0))
    max_x = min_x + float(getattr(monitors[0], "width", 0))
    max_y = min_y + float(getattr(monitors[0], "height", 0))
    for monitor in monitors[1:]:
        left = float(getattr(monitor, "x", 0))
        top = float(getattr(monitor, "y", 0))
        right = left + float(getattr(monitor, "width", 0))
        bottom = top + float(getattr(monitor, "height", 0))
        min_x = min(min_x, left)
        min_y = min(min_y, top)
        max_x = max(max_x, right)
        max_y = max(max_y, bottom)
    return {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y}


def overlay_skip_index(*, covers_current_monitor: bool, current_index: int | None) -> int | None:
    """Skip the launcher's monitor when that window already covers the work area (GNOME Wayland)."""
    if covers_current_monitor:
        return current_index
    return None


def overlay_plan(monitors: list[Any], skip_index: int | None = None) -> list[dict[str, Any]]:
    """One fullscreen overlay per monitor, equivalent to goshos' union backdrop actor."""
    plan: list[dict[str, Any]] = []
    for index, monitor in enumerate(monitors):
        if skip_index is not None and index == skip_index:
            continue
        plan.append(
            {
                "index": index,
                "x": float(getattr(monitor, "x", 0)),
                "y": float(getattr(monitor, "y", 0)),
                "width": float(getattr(monitor, "width", 0)),
                "height": float(getattr(monitor, "height", 0)),
            }
        )
    return plan


def overlay_window_style() -> dict[str, Any]:
    # goshos uses opacity 0 on a reactive Clutter actor. GTK surfaces with alpha 0
    # often drop hit-testing, so the CSS fill is a 1% black that still claims clicks.
    return {
        "decorated": False,
        "can_focus": False,
        "css_class": "goshos-backdrop",
        "css_background": "rgba(0, 0, 0, 0.01)",
        "defer_close": True,
    }
