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
    popup.win.show_results(results_update([pending, ready, later], Query(None, "/tmp")))
    popup.app.activated = None
    # Checking path is listed (Alt+1) but is not a selectable/activatable row.
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_Down)
    assert popup.win.results_view.selected_index == 2
    assert popup.press(Gdk.KEY_k, Gdk.ModifierType.CONTROL_MASK)
    assert popup.win.results_view.selected_index == 1
    assert popup.press(Gdk.KEY_1, Gdk.ModifierType.ALT_MASK)
    assert popup.app.activated is None
    assert popup.press(Gdk.KEY_2, Gdk.ModifierType.ALT_MASK)
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.name == "Firefox"


def test_places_system_path_and_spoken_math(popup: SearchPopup) -> None:
    assert "place" in popup.type_query("docs")
    assert "system" in popup.type_query("lock the screen")
    assert "path" in popup.type_query("/tmp")
    assert "calculator" in popup.type_query("two plus two")
    assert "settings" in popup.type_query("wifi")
    assert "units" in popup.type_query("convert 10 km to mi")
    assert "settings" in popup.type_query("open wifi settings")


def test_enter_activates_calculator_row(popup: SearchPopup) -> None:
    from gi.repository import Gdk

    kinds = popup.type_query("2+2")
    assert "calculator" in kinds
    popup.app.activated = None
    assert popup.press(Gdk.KEY_Return)
    chosen, alt = popup.app.activated
    assert alt is False
    assert chosen.kind == "calculator"


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
