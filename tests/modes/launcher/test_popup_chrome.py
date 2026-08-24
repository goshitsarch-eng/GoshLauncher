from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.popup_chrome import (
    IME_CANDIDATE_STYLE,
    OSK_POPOVER_STYLE,
    actor_has_style_class,
    actor_or_ancestor_has_style_class,
    backdrop_layer_for_input_chrome,
    chrome_add_method,
    ime_candidate_visible,
    input_chrome_to_raise,
    is_ime_candidate_actor,
    is_input_chrome_actor,
    is_osk_popover_actor,
    raise_input_chrome,
    raise_osk_chrome,
    should_raise_chrome_above,
    should_raise_on_input_chrome_allocation,
    should_schedule_input_chrome_raise,
    should_watch_input_chrome,
    should_watch_osk_popover,
    ui_group_children,
)


def test_chrome_add_method_prefers_top_chrome() -> None:
    assert chrome_add_method(True) == "addTopChrome"
    assert chrome_add_method(False) == "addChrome"


def test_style_class_and_input_chrome_helpers() -> None:
    osk = SimpleNamespace(style_class=OSK_POPOVER_STYLE, visible=True)
    ime = SimpleNamespace(style_class=IME_CANDIDATE_STYLE, visible=True)
    other = SimpleNamespace(style_class="popup-menu-boxpointer", visible=True)
    assert actor_has_style_class(osk, OSK_POPOVER_STYLE) is True
    assert actor_has_style_class(
        SimpleNamespace(has_style_class_name=lambda name: name == OSK_POPOVER_STYLE), OSK_POPOVER_STYLE
    )
    assert actor_has_style_class(other, OSK_POPOVER_STYLE) is False
    assert is_osk_popover_actor(SimpleNamespace(style_class=f"popup-menu {OSK_POPOVER_STYLE}")) is True
    assert is_ime_candidate_actor(ime) is True
    assert is_input_chrome_actor(ime) is True
    assert should_watch_osk_popover(osk, []) is True
    assert should_watch_input_chrome(ime, []) is True
    assert should_watch_osk_popover(osk, [osk]) is False
    child = SimpleNamespace(style_class=OSK_POPOVER_STYLE, get_parent=lambda: osk)
    osk.get_parent = lambda: None
    assert actor_or_ancestor_has_style_class(child, OSK_POPOVER_STYLE) is True


def test_raise_input_chrome_keys_then_accents_then_candidates() -> None:
    order: list[str] = []
    ui_group = SimpleNamespace()

    def _raise(actor: SimpleNamespace, sibling: SimpleNamespace) -> None:
        order.append(f"{actor.tag}>{sibling.tag}")

    ui_group.set_child_above_sibling = _raise
    popup = SimpleNamespace(tag="popup", visible=True, get_parent=lambda: ui_group)
    keyboard = SimpleNamespace(tag="kb", visible=True, get_parent=lambda: ui_group)
    accent = SimpleNamespace(tag="accent", visible=True, style_class=OSK_POPOVER_STYLE, get_parent=lambda: ui_group)
    hidden = SimpleNamespace(tag="hidden", visible=False, style_class=OSK_POPOVER_STYLE, get_parent=lambda: ui_group)
    candidate = SimpleNamespace(tag="ime", visible=True, style_class=IME_CANDIDATE_STYLE, get_parent=lambda: ui_group)
    ui_group.get_children = lambda: [accent, hidden, candidate, keyboard, popup]
    assert ui_group_children(ui_group) == [accent, hidden, candidate, keyboard, popup]
    raised = input_chrome_to_raise(ui_group, keyboard, popup)
    assert raised[0] is keyboard
    assert accent in raised
    assert candidate in raised
    assert should_raise_chrome_above(ui_group, keyboard, popup) is True
    assert should_raise_chrome_above(ui_group, hidden, popup) is False
    assert raise_input_chrome(ui_group, keyboard, popup) is True
    assert order[0] == "kb>popup"
    assert "accent>kb" in order
    assert ime_candidate_visible(ui_group) is True
    assert should_schedule_input_chrome_raise(False, True) is True
    assert should_schedule_input_chrome_raise(True, True) is False
    assert should_raise_on_input_chrome_allocation(True, True) is True
    assert raise_osk_chrome(ui_group, keyboard, popup) is True


def test_backdrop_layer_drops_below_osk_and_ime() -> None:
    assert backdrop_layer_for_input_chrome(False, False) == "overlay"
    assert backdrop_layer_for_input_chrome(True, False) == "top"
    assert backdrop_layer_for_input_chrome(False, True) == "top"
    assert backdrop_layer_for_input_chrome(True, True) == "top"
