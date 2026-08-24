"""Chrome stacking above always-on-top windows, from goshos popupChrome.js."""

from __future__ import annotations

from typing import Any

OSK_POPOVER_STYLE = "keyboard-subkeys-boxpointer"
IME_CANDIDATE_STYLE = "candidate-popup-boxpointer"


def chrome_add_method(has_top_chrome: bool) -> str:
    return "addTopChrome" if has_top_chrome else "addChrome"


def add_popup_chrome(layout_manager: Any, actor: Any) -> None:
    method = chrome_add_method(callable(getattr(layout_manager, "addTopChrome", None)))
    getattr(layout_manager, method)(actor)


def remove_popup_chrome(layout_manager: Any, actor: Any) -> None:
    layout_manager.removeChrome(actor)


def actor_has_style_class(actor: Any, name: str) -> bool:
    if not actor or not name:
        return False
    has_class = getattr(actor, "has_style_class_name", None)
    if callable(has_class):
        return bool(has_class(name))
    style = getattr(actor, "style_class", None)
    if not isinstance(style, str) or not style:
        return False
    return name in style.split()


def actor_or_ancestor_has_style_class(actor: Any, name: str, max_depth: int | None = None) -> bool:
    current = actor
    depth = 0
    limit = 8 if max_depth is None else max_depth
    while current and depth < limit:
        if actor_has_style_class(current, name):
            return True
        get_parent = getattr(current, "get_parent", None)
        current = get_parent() if callable(get_parent) else None
        depth += 1
    return False


def is_osk_popover_actor(actor: Any) -> bool:
    return actor_has_style_class(actor, OSK_POPOVER_STYLE)


def is_ime_candidate_actor(actor: Any) -> bool:
    return actor_has_style_class(actor, IME_CANDIDATE_STYLE)


def is_input_chrome_actor(actor: Any) -> bool:
    return is_osk_popover_actor(actor) or is_ime_candidate_actor(actor)


def should_watch_input_chrome(actor: Any, tracked: list[Any] | None) -> bool:
    if not is_input_chrome_actor(actor):
        return False
    if tracked and actor in tracked:
        return False
    return True


def should_watch_osk_popover(actor: Any, tracked: list[Any] | None) -> bool:
    return should_watch_input_chrome(actor, tracked)


def ui_group_children(ui_group: Any) -> list[Any]:
    if not ui_group or not callable(getattr(ui_group, "get_children", None)):
        return []
    kids = ui_group.get_children()
    return list(kids) if isinstance(kids, (list, tuple)) else []


def ime_candidate_visible(ui_group: Any) -> bool:
    for child in ui_group_children(ui_group):
        if is_ime_candidate_actor(child) and getattr(child, "visible", False):
            return True
    return False


def input_chrome_to_raise(ui_group: Any, keyboard_box: Any, popup: Any) -> list[Any]:
    actors: list[Any] = []
    if keyboard_box:
        actors.append(keyboard_box)
    accents: list[Any] = []
    candidates: list[Any] = []
    for child in ui_group_children(ui_group):
        if child is keyboard_box or child is popup:
            continue
        if is_osk_popover_actor(child):
            accents.append(child)
        elif is_ime_candidate_actor(child):
            candidates.append(child)
    return actors + accents + candidates


def osk_chrome_to_raise(ui_group: Any, keyboard_box: Any, popup: Any) -> list[Any]:
    return input_chrome_to_raise(ui_group, keyboard_box, popup)


def should_raise_chrome_above(ui_group: Any, actor: Any, sibling: Any) -> bool:
    if not ui_group or not actor or not sibling:
        return False
    if not callable(getattr(ui_group, "set_child_above_sibling", None)):
        return False
    if actor is sibling:
        return False
    if not getattr(actor, "visible", False):
        return False
    get_parent = getattr(actor, "get_parent", None)
    sibling_parent = getattr(sibling, "get_parent", None)
    actor_parent = get_parent() if callable(get_parent) else None
    other_parent = sibling_parent() if callable(sibling_parent) else None
    return actor_parent is ui_group and other_parent is ui_group


def raise_chrome_above(ui_group: Any, actor: Any, sibling: Any) -> bool:
    if not should_raise_chrome_above(ui_group, actor, sibling):
        return False
    try:
        ui_group.set_child_above_sibling(actor, sibling)
    except Exception:
        return False
    return True


def should_schedule_input_chrome_raise(has_pending_idle: bool, is_open: bool) -> bool:
    return bool(is_open) and not has_pending_idle


def should_raise_on_input_chrome_allocation(is_open: bool, actor_visible: bool) -> bool:
    return bool(is_open and actor_visible)


def raise_input_chrome(ui_group: Any, keyboard_box: Any, popup: Any) -> bool:
    raised = False
    sibling = popup
    for actor in input_chrome_to_raise(ui_group, keyboard_box, popup):
        if not raise_chrome_above(ui_group, actor, sibling):
            continue
        raised = True
        sibling = actor
    return raised


def raise_osk_chrome(ui_group: Any, keyboard_box: Any, popup: Any) -> bool:
    return raise_input_chrome(ui_group, keyboard_box, popup)
