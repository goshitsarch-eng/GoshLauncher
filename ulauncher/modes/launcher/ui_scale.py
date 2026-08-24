"""CSS px versus allocation px, from spotlight-goshos uiScale.js."""

from __future__ import annotations

from typing import Any


def _js_round(value: float) -> int:
    if value >= 0:
        return int(value + 0.5)
    return int(value - 0.5)


def theme_scale(scale: Any) -> float:
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not scale > 0:
        return 1
    return float(scale)


def theme_scale_from_context(ctx: Any) -> float:
    if not ctx:
        return 1
    if isinstance(ctx, dict):
        return theme_scale(ctx.get("scale_factor"))
    return theme_scale(getattr(ctx, "scale_factor", None))


def next_scale_listen_action(has_listener: bool, context: Any) -> str:
    if has_listener:
        return "keep"
    if not context:
        return "wait"
    return "listen"


def stage_px(logical: float, scale: Any = None) -> int:
    return _js_round(logical * theme_scale(scale))


def css_px(stage: float, scale: Any = None) -> int:
    return _js_round(stage / theme_scale(scale))
