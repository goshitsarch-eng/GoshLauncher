"""When an async Gio finish may repaint, from spotlight-goshos asyncPaint.js."""

from __future__ import annotations


def should_schedule_async_paint(has_pending_idle: bool, accept_paint: bool) -> bool:
    return accept_paint and not has_pending_idle


def should_run_async_paint(query_is_active: bool, accept_paint: bool) -> bool:
    return accept_paint and query_is_active
