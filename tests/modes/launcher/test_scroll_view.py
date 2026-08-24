from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.scroll_view import (
    apply_scroll_policy,
    attach_scroll_child,
    scroll_value_to_show_row,
    set_overlay_scrollbars,
    vertical_adjustment,
)


def test_scroll_value_to_show_row_matches_goshos() -> None:
    assert scroll_value_to_show_row(200, 40, 0, 0) == 0
    assert scroll_value_to_show_row(10, 40, 80, 200) == 10
    assert scroll_value_to_show_row(300, 40, 0, 200) == 140
    assert scroll_value_to_show_row(80, 40, 60, 200) == 60


def test_modern_scroll_view_helpers() -> None:
    modern = SimpleNamespace(child=None, h=None, v=None, overlay=None)

    def set_child(child: object) -> None:
        modern.child = child

    def set_policy(h: int, v: int) -> None:
        modern.h = h
        modern.v = v

    def get_vadjustment() -> dict[str, str]:
        return {"kind": "adj"}

    def set_overlay_scrolling(enabled: bool) -> None:
        modern.overlay = enabled

    modern.set_child = set_child
    modern.set_policy = set_policy
    modern.get_vadjustment = get_vadjustment
    modern.set_overlay_scrolling = set_overlay_scrolling

    attach_scroll_child(modern, "box")
    apply_scroll_policy(modern, 2, 3)
    set_overlay_scrollbars(modern, False)
    assert modern.child == "box"
    assert modern.h == 2
    assert modern.v == 3
    assert modern.overlay is False
    assert vertical_adjustment(modern) == {"kind": "adj"}


def test_legacy_scroll_view_helpers() -> None:
    legacy = SimpleNamespace(child=None, hscrollbar_policy=0, vscrollbar_policy=0)

    def add_child(child: object) -> None:
        legacy.child = child

    def get_vscroll_bar() -> SimpleNamespace:
        return SimpleNamespace(get_adjustment=lambda: {"kind": "bar"})

    legacy.add_child = add_child
    legacy.get_vscroll_bar = get_vscroll_bar

    attach_scroll_child(legacy, "box")
    apply_scroll_policy(legacy, 2, 3)
    assert legacy.child == "box"
    assert legacy.vscrollbar_policy == 3
    assert vertical_adjustment(legacy) == {"kind": "bar"}
