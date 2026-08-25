from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from tests.ui.conftest import GTK4_AVAILABLE

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")

if GTK4_AVAILABLE:
    from tests.ui.look_paint import display_available
    from tests.ui.popup_search import SearchPopup, open_search_popup
    from ulauncher.internals.query import Query
    from ulauncher.internals.results_update import results_update
    from ulauncher.modes.launcher.results import LauncherResult
    from ulauncher.modes.launcher.windows import WindowInfo
    from ulauncher.utils.settings import Settings


@pytest.fixture(scope="module")
def popup() -> Iterator[SearchPopup]:
    if not GTK4_AVAILABLE:
        pytest.skip("GTK 4 is not available")
    if not display_available():
        pytest.skip("no Gdk display")
    try:
        probe = open_search_popup()
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    yield probe
    probe.close()


def test_window_title_is_goshlauncher(popup: SearchPopup) -> None:
    assert popup.win.get_title() == "GoshLauncher"


def test_typed_calculator_and_bare_number(popup: SearchPopup) -> None:
    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    kinds = popup.type_query("=42")
    assert "calculator" in kinds
    kinds = popup.type_query("42")
    assert "calculator" not in kinds


def test_url_is_not_web_and_at_prefix_is_web(popup: SearchPopup) -> None:
    kinds = popup.type_query("example.com")
    assert "url" in kinds
    assert "web" not in kinds
    kinds = popup.type_query("@ cats")
    assert kinds == ["web"]


def test_hash_wifi_settings_versus_hex_color(popup: SearchPopup) -> None:
    kinds = popup.type_query("# wifi")
    assert "settings" in kinds
    assert "color" not in kinds
    kinds = popup.type_query("#ff0000")
    assert "color" in kinds
    assert "settings" not in kinds


def test_units_clock_and_file_ext_denylist(popup: SearchPopup) -> None:
    assert "units" in popup.type_query("10 km to mi")
    assert "clock" in popup.type_query("time")
    kinds = popup.type_query("node.js")
    assert "url" not in kinds


def test_command_prefix_is_off_by_default(popup: SearchPopup) -> None:
    kinds = popup.type_query("! definitely-not-a-ulauncher-binary-xyz")
    assert "command" not in kinds


def test_keyboard_nav_and_alt_number_skips_checking_path(popup: SearchPopup) -> None:
    from gi.repository import Gdk

    pending = LauncherResult(name="Checking path", kind="path", activatable=False, actions={})
    ready = LauncherResult(name="Firefox", kind="app", payload={"app_id": "firefox.desktop"})
    later = LauncherResult(name="Files", kind="app", payload={"app_id": "files.desktop"})
    popup.win._chrome["show_numbers"] = True
    popup.win.set_input("")
    popup.win.show_results(results_update([pending, ready, later], Query(None, "/tmp")))
    popup.app.activated = None
    popup.app.closed = False
    # Checking path is listed (Alt+1) but is not a selectable/activatable row.
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_Down)
    assert popup.win.results_view.selected_index == 2
    assert popup.press(Gdk.KEY_k, Gdk.ModifierType.CONTROL_MASK)
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_Tab)
    assert popup.win.results_view.selected_index == 2
    assert popup.press(Gdk.KEY_n, Gdk.ModifierType.CONTROL_MASK)
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_End)
    assert popup.win.results_view.selected_index == 2
    assert popup.press(Gdk.KEY_Home)
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_Page_Down)
    assert popup.win.results_view.selected_index == 2
    assert popup.press(Gdk.KEY_p, Gdk.ModifierType.CONTROL_MASK)
    assert popup.win.results_view.selected_index == 1
    popup.app.preferences_shown = False
    assert popup.press(Gdk.KEY_comma, Gdk.ModifierType.CONTROL_MASK)
    assert popup.app.preferences_shown is True
    assert popup.press(Gdk.KEY_1, Gdk.ModifierType.ALT_MASK)
    assert popup.app.activated is None
    assert popup.press(Gdk.KEY_2, Gdk.ModifierType.ALT_MASK)
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.name == "Firefox"
    assert popup.press(Gdk.KEY_Escape)
    assert popup.app.closed is True


def test_places_system_path_and_spoken_math(popup: SearchPopup) -> None:
    assert "place" in popup.type_query("docs")
    assert "system" in popup.type_query("lock the screen")
    assert "path" in popup.type_query("/tmp")
    assert "calculator" in popup.type_query("two plus two")
    assert "settings" in popup.type_query("wifi")
    assert "units" in popup.type_query("convert 10 km to mi")
    assert "settings" in popup.type_query("open wifi settings")


def test_enter_activates_calculator_row(popup: SearchPopup) -> None:
    from unittest.mock import patch

    from gi.repository import Gdk

    from ulauncher.internals.query import Query
    from ulauncher.modes.launcher.mode import LauncherMode

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    assert "Calculator" in popup.header_names()
    popup.app.activated = None
    copied: list[str] = []

    def emit(name: str, data: object = None) -> None:
        if name == "app:copy_and_close":
            copied.append(str(data))

    assert popup.press(Gdk.KEY_Return)
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.kind == "calculator"
    with patch("ulauncher.modes.launcher.mode._events.emit", emit):
        LauncherMode().activate_result("activate", chosen, Query(None, "2+2"), lambda *_args: None)
    assert copied == ["4"]
    for query, kind in (("10 km to mi", "units"), ("red", "color"), ("time", "clock")):
        copied.clear()
        assert kind in popup.type_query(query)
        row = next(item for item in popup.win.results_view.get_result_objects() if getattr(item, "kind", "") == kind)
        with patch("ulauncher.modes.launcher.mode._events.emit", emit):
            LauncherMode().activate_result("activate", row, Query(None, query), lambda *_args: None)
        assert copied == [row.name]


def test_dollar_and_dot_prefixes_need_a_space() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    windows = [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)]
    try:
        probe = open_search_popup(home_windows=windows)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        kinds = probe.type_query("$ firefox")
        assert kinds == ["window"]
        kinds = probe.type_query("close firefox")
        assert "window-close" in kinds
        kinds = probe.type_query("workspace 2")
        assert "workspace" in kinds
        kinds = probe.type_query("workspace two")
        assert "workspace" in kinds
        kinds = probe.type_query("kill firefox")
        assert "window-close" in kinds
        kinds = probe.type_query("force quit firefox")
        assert "window-close" in kinds
        home_kinds = probe.type_query("$HOME")
        assert "window" not in home_kinds
        bashrc = probe.type_query(".bashrc")
        assert "file" not in bashrc
        notes = probe.type_query(". notes")
        assert "url" not in notes
        assert "calculator" not in notes
        assert "web" not in notes
    finally:
        probe.close()


def test_empty_state_windows_first_on_popos() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    settings = Settings()
    settings.look_id = "popos"
    settings.applied_look = "popos"
    settings.result_order = "windows-first"
    settings.enable_empty_suggestions = True
    settings.enable_application_mode = True
    settings.enable_window_search = True
    apps = [SimpleNamespace(name="Firefox", icon="firefox", app_id="firefox.desktop")]
    windows = [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)]
    try:
        probe = open_search_popup(settings=settings, home_apps=apps, home_windows=windows)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        kinds = probe.kinds()
        assert kinds[:2] == ["window", "app"]
        assert probe.names()[:2] == ["Mozilla Firefox", "Firefox"]
    finally:
        probe.close()


def _web_fallback_settings() -> Settings:
    settings = Settings()
    settings.show_web_search = True
    for attr in (
        "enable_application_mode",
        "enable_url_open",
        "enable_path_open",
        "enable_places",
        "enable_bookmarks",
        "enable_calculator",
        "enable_unit_convert",
        "enable_color_hex",
        "enable_time_date",
        "enable_window_search",
        "enable_system_actions",
        "enable_settings_search",
        "enable_recent_files",
        "enable_command_run",
    ):
        setattr(settings, attr, False)
    return settings


def test_web_fallback_and_at_prefix_with_fallback_off() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    try:
        probe = open_search_popup(settings=_web_fallback_settings())
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        kinds = probe.type_query("zzzxqwerty999nomatch")
        assert kinds == ["web"]
        assert any(name.startswith("Search Google for") for name in probe.names())
    finally:
        probe.close()

    settings = Settings()
    settings.show_web_search = False
    try:
        probe = open_search_popup(settings=settings)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        assert probe.type_query("@ cats") == ["web"]
        kinds = probe.type_query("zzzxqwerty999nomatch")
        assert "web" not in kinds
    finally:
        probe.close()


def test_javascript_is_not_a_url_and_mailto_is(popup: SearchPopup) -> None:
    kinds = popup.type_query("javascript:alert(1)")
    assert "url" not in kinds
    assert "url" in popup.type_query("mailto:nin@example.com")
    assert "url" in popup.type_query("localhost:3000")
    assert "url" not in popup.type_query("https://example.com/foo bar")


def test_more_goshos_queries(popup: SearchPopup) -> None:
    assert "color" in popup.type_query("rgb 255 0 0")
    assert "color" in popup.type_query("hsl(0deg 100% 50%)")
    assert "color" in popup.type_query("hwb(0 0% 0%)")
    assert "clock" in popup.type_query("tomorrow")
    assert "units" in popup.type_query("32 f to c")
    assert "calculator" in popup.type_query("half of 80")
    assert "place" in popup.type_query("open my documents")
    assert "calculator" in popup.type_query("2pi")
    assert "calculator" in popup.type_query("what is 2+2")
    assert "clock" in popup.type_query("yesterday")
    assert "color" in popup.type_query("red")
    color = next(row for row in popup.win.results_view.get_result_objects() if getattr(row, "kind", "") == "color")
    assert color.name == "#ff0000"
    assert "url" in popup.type_query("sftp://nas.example/share")
    assert "url" in popup.type_query("smb://nas/Public")
    assert "url" in popup.type_query("::1")
    assert "url" in popup.type_query("file:///home/u/My Documents")
    file_row = next(row for row in popup.win.results_view.get_result_objects() if getattr(row, "kind", "") == "url")
    assert file_row.payload.get("url") == "file:///home/u/My%20Documents"
    assert "url" in popup.type_query("file://localhost/home/u/My Documents")
    localhost = next(row for row in popup.win.results_view.get_result_objects() if getattr(row, "kind", "") == "url")
    assert localhost.payload.get("url") == "file:///home/u/My%20Documents"
    assert "url" in popup.type_query("sftp://nas/My Documents")
    sftp = next(row for row in popup.win.results_view.get_result_objects() if getattr(row, "kind", "") == "url")
    assert sftp.payload.get("url") == "sftp://nas/My%20Documents"
    assert "system" in popup.type_query("lock now")
    assert "units" in popup.type_query("how many miles are there in 10 km")
    assert "calculator" in popup.type_query("what is the answer to 2+2")


def test_command_prefix_when_enabled() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    settings = Settings()
    settings.enable_command_run = True
    try:
        probe = open_search_popup(settings=settings)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        kinds = probe.type_query("! definitely-not-a-ulauncher-binary-xyz")
        assert "command" in kinds
    finally:
        probe.close()


def test_krunner_look_applies_compact_density() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    settings = Settings()
    settings.look_id = "krunner"
    settings.applied_look = ""
    try:
        probe = open_search_popup(settings=settings)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        classes = probe.css_classes()
        assert "gosh-theme-krunner" in classes
        assert "gosh-density-compact" in classes
        assert "gosh-no-search-icon" not in classes
        assert "calculator" in probe.type_query("2+2")
        assert probe.number_hints()[:1] == ["1"]
        sizes = probe.icon_pixel_sizes()
        assert sizes
        assert sizes[0] == 16
        calc = next(
            widget for widget in probe.win.results_view._widgets if getattr(widget.result, "kind", "") == "calculator"
        )
        assert calc.result.description
        assert calc.result.compact is False
    finally:
        probe.close()


def test_rofi_hides_search_icon() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    settings = Settings()
    settings.look_id = "rofi"
    settings.applied_look = ""
    try:
        probe = open_search_popup(settings=settings)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        classes = probe.css_classes()
        assert "gosh-theme-rofi" in classes
        assert "gosh-no-search-icon" in classes
        assert probe.win.search_icon.get_visible() is False
        assert probe.win.prompt_input.get_placeholder_text() == "Filter"
        assert "calculator" in probe.type_query("2+2")
        from ulauncher.ui import gtk4

        for widget in probe.win.results_view._widgets:
            assert not any(child.has_css_class("item-icon") for child in gtk4.list_children(widget.item_container))
    finally:
        probe.close()


def test_spotlight_popup_keeps_default_look_css(popup: SearchPopup) -> None:
    classes = popup.css_classes()
    assert "app" in classes
    assert "gosh-theme-spotlight" in classes
    assert "gosh-density-comfortable" in classes
    assert popup.win.prompt_input.get_placeholder_text() == "Search apps..."


def test_no_results_copy_when_web_fallback_is_off() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    settings = _web_fallback_settings()
    settings.show_web_search = False
    try:
        probe = open_search_popup(settings=settings)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        assert probe.type_query("zzzxqwerty999nomatch") == []
        copy = probe.no_results_copy()
        assert copy[0] == "No Results"
        assert copy[1] == 'No results for "zzzxqwerty999nomatch"'
        assert probe.win.results_view.get_visible() is True
    finally:
        probe.close()


def test_bookmarks_recents_missing_path_and_terminal(popup: SearchPopup) -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    hits = [
        {
            "title": "UniqueBookmarkLabelXYZ",
            "uri": "file:///tmp",
            "description": "/tmp",
            "icon": "folder-symbolic",
        }
    ]
    recents = [
        {
            "title": "UniqueRecentNotesXYZ.txt",
            "uri": "file:///tmp/UniqueRecentNotesXYZ.txt",
            "description": "/tmp",
            "icon": "text-x-generic-symbolic",
        }
    ]
    try:
        probe = open_search_popup(bookmark_hits=hits, recent_hits=recents)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        assert "bookmark" in probe.type_query("UniqueBookmarkLabelXYZ")
        assert "file" in probe.type_query("UniqueRecentNotesXYZ")
    finally:
        probe.close()
    assert "path" in popup.type_query("/tmp")
    assert "Open in Terminal" in popup.names()
    popup.type_query("/no/such/goshlauncher/path-xyz")
    paths = [row for row in popup.win.results_view.get_result_objects() if getattr(row, "kind", "") == "path"]
    assert any(row.description == "Path not found" for row in paths)


def test_click_row_activates_and_click_outside_closes(popup: SearchPopup) -> None:
    from types import SimpleNamespace

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    popup.app.activated = None
    calc = next(
        widget for widget in popup.win.results_view._widgets if getattr(widget.result, "kind", "") == "calculator"
    )
    gesture = SimpleNamespace(
        get_current_button=lambda: 1,
        get_device=lambda: None,
        set_state=lambda *_args: None,
    )
    calc.on_pointer_press(gesture, 1, 0.0, 0.0)
    calc.on_click(gesture, 1, 0.0, 0.0)
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.kind == "calculator"
    popup.app.closed = False
    popup.win.on_backdrop_released(SimpleNamespace(), 1, -8.0, -8.0)
    assert popup.app.closed is True


def test_typed_app_offers_new_window_when_running() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    app = SimpleNamespace(
        name="Firefox",
        icon="firefox",
        app_id="firefox.desktop",
        _executable="firefox",
        actions={
            "launch": {"name": "Launch"},
            "action:new-window": {"name": "New Window"},
            "action:private": {"name": "Private"},
        },
    )
    windows = [WindowInfo(wid="0x1", title="Mozilla Firefox", wm_class="firefox.Firefox", desktop=0, pid=11)]
    try:
        probe = open_search_popup(typed_apps=[app], home_windows=windows)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        kinds = probe.type_query("open firefox")
        assert "app" in kinds
        assert "app-action" in kinds
        assert "window" in kinds
        assert "New window — Firefox" in probe.names()
        assert "Private — Firefox" in probe.names()
        assert "Applications" in probe.header_names()
        assert "Actions" in probe.header_names()
        assert "Windows" in probe.header_names()
    finally:
        probe.close()


def test_touch_tap_activates_live_calculator_row(popup: SearchPopup) -> None:
    from types import SimpleNamespace

    from ulauncher.modes.launcher.result_pointer import TOUCH_TAP_SLOP

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    popup.app.activated = None
    calc = next(
        widget for widget in popup.win.results_view._widgets if getattr(widget.result, "kind", "") == "calculator"
    )

    def event(kind: str, y: float) -> SimpleNamespace:
        return SimpleNamespace(
            get_event_type=lambda: SimpleNamespace(value_nick=kind),
            get_position=lambda: (0.0, y),
        )

    calc.on_touch_event(None, event("touch-begin", 10.0))
    calc.on_touch_event(None, event("touch-end", 12.0))
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.kind == "calculator"

    popup.app.activated = None
    calc.on_touch_event(None, event("touch-begin", 10.0))
    calc.on_touch_event(None, event("touch-update", 10.0 + TOUCH_TAP_SLOP + 4))
    calc.on_touch_event(None, event("touch-end", 10.0 + TOUCH_TAP_SLOP + 4))
    assert popup.app.activated is None


def test_ime_preedit_does_not_activate(popup: SearchPopup) -> None:
    from unittest.mock import patch

    from gi.repository import Gdk

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    popup.app.activated = None
    with patch("ulauncher.ui.ulauncher_window._read_entry_preedit", return_value="あ"):
        assert popup.press(Gdk.KEY_Return) is False
    assert popup.app.activated is None


def test_live_prefs_keep_selected_row(popup: SearchPopup) -> None:
    from ulauncher.modes.launcher.prefs_live import live_pref_actions

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    assert "Calculator" in popup.header_names()
    popup.win.results_view.select_jump(0)
    chosen = popup.win.results_view.get_active_result()
    assert chosen is not None
    assert getattr(chosen, "kind", "") == "calculator"
    name = chosen.name
    popup.settings.show_section_headers = False
    popup.win.apply_live_prefs(live_pref_actions(["show_section_headers"]))
    popup.app.query_changed(popup.win.prompt_input.get_text())
    popup.pump_idle()
    assert "calculator" in popup.kinds()
    assert popup.header_names() == []
    active = popup.win.results_view.get_active_result()
    assert active is not None
    assert active.kind == "calculator"
    assert active.name == name


def test_popos_compact_icons_stay_larger_than_krunner() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    popos = Settings()
    popos.look_id = "popos"
    popos.applied_look = "popos"
    popos.row_density = "compact"
    popos.icon_size = 36
    try:
        pop_probe = open_search_popup(settings=popos)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        assert "calculator" in pop_probe.type_query("2+2")
        pop_sizes = pop_probe.icon_pixel_sizes()
        assert pop_sizes
        pop_size = pop_sizes[0]
    finally:
        pop_probe.close()

    krunner = Settings()
    krunner.look_id = "krunner"
    krunner.applied_look = ""
    try:
        run_probe = open_search_popup(settings=krunner)
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open search popup: {exc}")
    try:
        assert "calculator" in run_probe.type_query("2+2")
        run_sizes = run_probe.icon_pixel_sizes()
        assert run_sizes
        run_size = run_sizes[0]
    finally:
        run_probe.close()
    assert pop_size > run_size
    assert run_size == 16
    assert pop_size == 29
