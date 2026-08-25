from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.focus_loss import (
    focus_is_ime_candidate,
    focus_is_on_screen_keyboard,
    focus_is_search_entry,
    focus_loss_action,
    gtk_window_focus_action,
    point_in_rect,
    popup_chrome_should_focus,
    prompt_click_should_drag,
    prompt_click_should_refocus,
    prompt_click_target,
    result_row_should_focus,
    should_capture_keys,
    should_run_refocus,
)


def test_rows_and_chrome_do_not_take_focus() -> None:
    assert result_row_should_focus() is False
    assert popup_chrome_should_focus() is False


def test_focus_is_search_entry() -> None:
    entry = SimpleNamespace(contains=lambda other: other == "clutter-text")
    assert focus_is_search_entry(entry, entry) is True
    assert focus_is_search_entry("clutter-text", entry) is True
    assert focus_is_search_entry("row", entry) is False
    assert focus_is_search_entry(None, entry) is False


def test_focus_loss_action_matches_goshos() -> None:
    assert focus_loss_action(False, False, False, False) == "refocus-entry"
    assert focus_loss_action(True, True, False, False) == "refocus-entry"
    assert focus_loss_action(True, False, False, False) == "close"
    assert focus_loss_action(True, False, False, False, True) == "ignore"
    assert focus_loss_action(True, False, False, False, False, True) == "ignore"
    assert focus_loss_action(True, False, True, False) == "refocus-entry"
    assert focus_loss_action(True, False, True, True) == "ignore"


def test_capture_keys_and_refocus() -> None:
    assert should_capture_keys(True, False, False, False) is True
    assert should_capture_keys(True, True, True, False) is True
    assert should_capture_keys(True, True, False, True) is True
    assert should_capture_keys(True, True, False, False) is False
    assert should_capture_keys(True, True, False, False, True) is True
    assert should_capture_keys(True, True, False, False, False, True) is True
    assert should_capture_keys(False, False, False, False) is False
    assert should_run_refocus(True, True) is True
    assert should_run_refocus(False, True) is False
    assert should_run_refocus(True, False) is False


def test_gtk_window_focus_action() -> None:
    entry = object()
    assert gtk_window_focus_action(False, None, entry) == "close"
    assert gtk_window_focus_action(True, None, entry) == "refocus-entry"
    assert gtk_window_focus_action(True, entry, entry) == "ignore"
    assert gtk_window_focus_action(True, object(), entry) == "refocus-entry"
    assert gtk_window_focus_action(False, None, entry, ime_panel=True) == "ignore"
    assert gtk_window_focus_action(False, None, entry, osk_contains_focus=True) == "ignore"
    candidate = SimpleNamespace(has_css_class=lambda name: name == "candidate-popup-boxpointer")
    assert gtk_window_focus_action(True, candidate, entry) == "ignore"


def test_prompt_click_search_icon_and_padding_refocus() -> None:
    icon = (0.0, 0.0, 20.0, 20.0)
    entry = (24.0, 0.0, 200.0, 20.0)
    assert prompt_click_target(8.0, 10.0, icon, entry) == "search-icon"
    assert prompt_click_target(100.0, 10.0, icon, entry) == "entry"
    assert prompt_click_target(12.0, 40.0, icon, entry) == "padding"
    assert prompt_click_should_refocus("search-icon") is True
    assert prompt_click_should_refocus("padding") is True
    assert prompt_click_should_refocus("entry") is False
    assert prompt_click_should_drag("padding") is False
    assert prompt_click_should_drag("search-icon") is False
    assert point_in_rect(0.0, 0.0, (0.0, 0.0, 0.0, 0.0)) is False


def test_osk_and_ime_helpers() -> None:
    osk_key = SimpleNamespace(extended_key=True)
    assert focus_is_on_screen_keyboard(osk_key, None) is True
    box = SimpleNamespace(contains=lambda other: other == "key")
    assert focus_is_on_screen_keyboard("key", box) is True
    candidate = SimpleNamespace(has_css_class=lambda name: name == "candidate-popup-boxpointer")
    assert focus_is_ime_candidate(candidate) is True
    assert focus_is_ime_candidate(SimpleNamespace(has_css_class=lambda _name: False)) is False
