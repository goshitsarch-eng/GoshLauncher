"""Whether focus should close the popup or return to the entry.

Ported from Spotlight-goshos focusLoss.js.
"""

from __future__ import annotations

from typing import Any

IME_CANDIDATE_STYLE = "candidate-popup-boxpointer"
OSK_POPOVER_STYLE = "keyboard-subkeys-boxpointer"


def result_row_should_focus() -> bool:
    return False


def popup_chrome_should_focus() -> bool:
    return False


def focus_is_search_entry(focus: Any, entry: Any) -> bool:
    if not focus or not entry:
        return False
    if focus is entry:
        return True
    contains = getattr(entry, "contains", None)
    return callable(contains) and bool(contains(focus))


def _has_style_class(actor: Any, name: str) -> bool:
    if not actor or not name:
        return False
    has_class = getattr(actor, "has_css_class", None) or getattr(actor, "has_style_class_name", None)
    if callable(has_class):
        return bool(has_class(name))
    style = getattr(actor, "style_class", None)
    if isinstance(style, str) and style:
        return name in style.split()
    return False


def actor_or_ancestor_has_style_class(actor: Any, name: str, max_depth: int = 8) -> bool:
    current = actor
    depth = 0
    while current and depth < max_depth:
        if _has_style_class(current, name):
            return True
        parent = getattr(current, "get_parent", None)
        current = parent() if callable(parent) else None
        depth += 1
    return False


def focus_is_on_screen_keyboard(focus: Any, keyboard_box: Any = None) -> bool:
    if not focus:
        return False
    if getattr(focus, "extended_key", None) or getattr(focus, "_extended_keys", None):
        return True
    if not keyboard_box:
        return False
    if focus is keyboard_box:
        return True
    contains = getattr(keyboard_box, "contains", None)
    return callable(contains) and bool(contains(focus))


def focus_is_ime_candidate(focus: Any) -> bool:
    return actor_or_ancestor_has_style_class(focus, IME_CANDIDATE_STYLE)


def focus_loss_action(
    has_focus: bool,
    is_stage: bool,
    popup_contains_focus: bool,
    focus_is_entry: bool,
    osk_contains_focus: bool = False,
    ime_contains_focus: bool = False,
) -> str:
    if not has_focus or is_stage:
        return "refocus-entry"
    if osk_contains_focus or ime_contains_focus:
        return "ignore"
    if not popup_contains_focus:
        return "close"
    if not focus_is_entry:
        return "refocus-entry"
    return "ignore"


def should_capture_keys(
    visible: bool,
    has_focus: bool,
    is_stage: bool,
    popup_contains_focus: bool,
    osk_contains_focus: bool = False,
    ime_contains_focus: bool = False,
) -> bool:
    if not visible:
        return False
    if not has_focus or is_stage or osk_contains_focus or ime_contains_focus:
        return True
    return popup_contains_focus


def should_run_refocus(is_open: bool, visible: bool) -> bool:
    return bool(is_open and visible)


def point_in_rect(x: float, y: float, rect: tuple[float, float, float, float]) -> bool:
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def prompt_click_target(
    x: float,
    y: float,
    icon_rect: tuple[float, float, float, float],
    entry_rect: tuple[float, float, float, float],
) -> str:
    """Which prompt child a click hit. Search icon and empty padding are chrome."""
    if point_in_rect(x, y, icon_rect):
        return "search-icon"
    if point_in_rect(x, y, entry_rect):
        return "entry"
    return "padding"


def prompt_click_should_refocus(target: str) -> bool:
    """Click the magnifier or empty padding — the next letter must reach the entry."""
    return target in {"search-icon", "padding"}


def prompt_click_should_drag(target: str) -> bool:  # noqa: ARG001
    """Goshos chrome is a fixed work-area actor, not a movable GTK window."""
    return False


def gtk_window_focus_action(
    window_active: bool,
    focus: Any,
    entry: Any,
    *,
    ime_panel: bool = False,
    osk_contains_focus: bool = False,
) -> str:
    """Map GTK window focus onto the goshos focus-loss table.

    Alt-tab to another window is close. A null focus widget while the window is
    still active is the GNOME 48 chrome-click case and returns to the entry.
    An IBus/Fcitx lookup or OSK long-press is not alt-tab.
    """
    ime_focus = bool(ime_panel) or focus_is_ime_candidate(focus)
    osk_focus = bool(osk_contains_focus) or focus_is_on_screen_keyboard(focus)
    if not window_active:
        if ime_focus or osk_focus:
            return "ignore"
        return focus_loss_action(True, False, False, False, False, False)
    return focus_loss_action(
        bool(focus),
        False,
        focus is not None,
        focus_is_search_entry(focus, entry),
        osk_focus,
        ime_focus,
    )
