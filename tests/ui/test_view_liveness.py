from __future__ import annotations

from types import SimpleNamespace

from ulauncher.ui.preferences.views import prefs_view_reload_action


def test_prefs_view_reload_stops_when_toplevel_is_gone() -> None:
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: None)
    assert prefs_view_reload_action(None, widget) == "stop"


def test_prefs_view_reload_stops_when_destroyed() -> None:
    toplevel = SimpleNamespace(in_destruction=lambda: True)
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: True, get_native=lambda: object())
    assert prefs_view_reload_action(toplevel, widget) == "stop"
    live = SimpleNamespace(in_destruction=lambda: False)
    dying = SimpleNamespace(in_destruction=lambda: True, get_mapped=lambda: True, get_native=lambda: object())
    assert prefs_view_reload_action(live, dying) == "stop"


def test_prefs_view_reload_skips_unrealized_unmapped_widget() -> None:
    toplevel = SimpleNamespace(in_destruction=lambda: False)
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: None)
    assert prefs_view_reload_action(toplevel, widget) == "skip"


def test_prefs_view_reload_keeps_hidden_mapped_or_realized_pages() -> None:
    toplevel = SimpleNamespace(in_destruction=lambda: False)
    hidden = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: object())
    mapped = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: True, get_native=lambda: None)
    assert prefs_view_reload_action(toplevel, hidden) == "reload"
    assert prefs_view_reload_action(toplevel, mapped) == "reload"
