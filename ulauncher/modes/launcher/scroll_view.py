"""Scroll helpers, ported from spotlight-goshos scrollView.js.

Compatibility scroll views expose either set_child / get_vadjustment or the
older add_child / get_vscroll_bar pair. Feature-detect so tests and
hosts can speak both without a version branch.
"""

from __future__ import annotations

from typing import Any, Optional


def attach_scroll_child(scroll_view: Any, child: Any) -> None:
    setter = getattr(scroll_view, "set_child", None)
    if callable(setter):
        setter(child)
        return
    adder = getattr(scroll_view, "add_child", None)
    if callable(adder):
        adder(child)


def apply_scroll_policy(scroll_view: Any, h_policy: Any, v_policy: Any) -> None:
    setter = getattr(scroll_view, "set_policy", None)
    if callable(setter):
        setter(h_policy, v_policy)
        return
    scroll_view.hscrollbar_policy = h_policy
    scroll_view.vscrollbar_policy = v_policy


def set_overlay_scrollbars(scroll_view: Any, enabled: bool) -> None:
    # overlay bars sit on the row and hide Alt+1-9 hints
    setter = getattr(scroll_view, "set_overlay_scrollbars", None)
    if not callable(setter):
        setter = getattr(scroll_view, "set_overlay_scrolling", None)
    if callable(setter):
        setter(enabled)


def vertical_adjustment(scroll_view: Any) -> Any:
    getter = getattr(scroll_view, "get_vadjustment", None)
    if callable(getter):
        return getter()
    bar_getter = getattr(scroll_view, "get_vscroll_bar", None)
    if not callable(bar_getter):
        return None
    bar = bar_getter()
    if bar is None:
        return None
    adj_getter = getattr(bar, "get_adjustment", None)
    return adj_getter() if callable(adj_getter) else None


def scroll_value_to_show_row(row_y: float, row_height: float, value: float, page_size: float) -> float:
    # page_size is 0 before the first allocate; writing that offset jumps the list
    if page_size <= 0:
        return value
    if row_y < value:
        return row_y
    if row_y + row_height > value + page_size:
        return row_y + row_height - page_size
    return value


def apply_scroll_value(adjustment: Optional[Any], value: float) -> None:
    if adjustment is None:
        return
    setter = getattr(adjustment, "set_value", None)
    if callable(setter):
        setter(value)
