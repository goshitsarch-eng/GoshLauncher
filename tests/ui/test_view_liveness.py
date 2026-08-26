from __future__ import annotations

from types import SimpleNamespace

from ulauncher.ui.preferences.views import prefs_view_reload_action


def test_prefs_view_reload_stops_when_toplevel_is_gone() -> None:
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: None)
    assert prefs_view_reload_action(None, widget) == "stop"


def test_prefs_view_reload_stops_when_destroyed() -> None:
    native = object()
    toplevel = SimpleNamespace(in_destruction=lambda: True)
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: True, get_native=lambda: native)
    assert prefs_view_reload_action(toplevel, widget) == "stop"
    live = SimpleNamespace(in_destruction=lambda: False)
    dying = SimpleNamespace(in_destruction=lambda: True, get_mapped=lambda: True, get_native=lambda: native)
    assert prefs_view_reload_action(live, dying) == "stop"


def test_prefs_view_reload_skips_unrealized_unmapped_widget() -> None:
    toplevel = SimpleNamespace(in_destruction=lambda: False)
    widget = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: None)
    assert prefs_view_reload_action(toplevel, widget) == "skip"


def test_prefs_view_reload_keeps_hidden_mapped_or_realized_pages() -> None:
    native = object()
    toplevel = SimpleNamespace(in_destruction=lambda: False)
    hidden = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: False, get_native=lambda: native)
    mapped = SimpleNamespace(in_destruction=lambda: False, get_mapped=lambda: True, get_native=lambda: None)
    assert prefs_view_reload_action(toplevel, hidden) == "reload"
    assert prefs_view_reload_action(toplevel, mapped) == "reload"


def test_closed_window_stops_receiving_monitor_hotplugs() -> None:
    from tests.ui.look_paint import pump
    from tests.ui.popup_search import open_search_popup
    from ulauncher.utils.settings import Settings

    # The monitor model belongs to the display and outlives the window, which is destroyed and
    # rebuilt on every popup open, so a connection left behind repositions dead windows forever.
    fired: list[int] = []
    models = []
    for index in range(3):
        popup = open_search_popup(settings=Settings())
        window = popup.win
        window._ensure_monitor_watch()
        models.append(window._monitors_model)
        window._on_monitors_changed = lambda i=index: fired.append(i)
        window.close()
        pump(20)

    assert all(model is models[0] for model in models)
    models[0].emit("items-changed", 0, 0, 0)
    pump(10)
    assert fired == []
