from __future__ import annotations

from pathlib import Path

import pytest

from tests.ui.conftest import GTK4_AVAILABLE

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")


def test_preferences_view_omits_ulauncher_color_theme_and_window_shadow() -> None:
    source = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "preferences.py"
    text = source.read_text()
    assert "window_shadow" not in text
    assert "Color theme" not in text
    assert "theme_name" not in text
    assert "look_prefs_search_text()" in text
    assert "engine_prefs_search_text()" in text
    assert "Jump keys" not in text
    assert "Number of frequent apps" not in text
    assert "max_recent_apps" not in text
    about_path = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "about.py"
    assert not about_path.exists()


def test_help_page_documents_goshos_keyboard() -> None:
    source = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "help.py"
    text = source.read_text()
    assert "Alt+Number/Letter" not in text
    assert "Jump to result by position" not in text
    assert "pack_start" not in text
    assert "Alt+1" in text
    assert "Ctrl+N / Ctrl+P" in text
    assert "Checking" in text
    assert "Ctrl+Space" in text

    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.ui.preferences.views.help import build_help_page

    page = build_help_page()
    assert page.get_title() == "Help"


def test_goshos_pref_page_titles() -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.modes.launcher.looks import LOOKS
    from ulauncher.ui.preferences.views.preferences import PreferencesView

    view = PreferencesView()
    try:
        titles = [page.get_title() for page in view.goshos_pages()]
        assert titles == ["Shortcut", "Appearance", "Features", "Web Search", "About"]
        assert int(view._look_combo.get_selected()) >= 0
        assert int(view._look_combo.get_selected()) < len(LOOKS)
        assert view._engine_combo.get_model().get_n_items() == 9
    finally:
        view.unbind_settings()


def test_prefs_window_default_size_matches_goshos() -> None:
    from ulauncher.ui.preferences.preferences_window import WINDOW_DEFAULT_HEIGHT, WINDOW_DEFAULT_WIDTH

    assert (WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT) == (680, 720)


_GTK3_WIDGET_APIS = (
    r"(?<!gtk4)\.pack_start\(",
    r"(?<!gtk4)\.pack_end\(",
    r"(?<!gtk4)\.show_all\(",
    r"(?<!gtk4)\.get_children\(",
    r"Gtk\.Image\.new_from_surface",
    r"\.set_image\(",
    r"\.add_buttons\(",
    r"dialog\.run\(",
)


def test_ui_package_does_not_install_gtk3_compat() -> None:
    init = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "__init__.py"
    gtk4 = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "gtk4.py"
    assert "install_compat" not in init.read_text()
    assert "def install_compat" not in gtk4.read_text()


def test_legacy_pref_pages_use_gtk4_helpers() -> None:
    import re

    root = Path(__file__).resolve().parents[2] / "ulauncher" / "ui"
    files = [path for path in root.rglob("*.py") if path.name != "gtk4.py"]
    for path in files:
        text = path.read_text()
        for pattern in _GTK3_WIDGET_APIS:
            match = re.search(pattern, text)
            assert match is None, f"{path} still uses GTK3 {pattern}: {match.group(0) if match else ''}"
        if path.name in {"sidebar_layout.py", "shortcuts.py", "extensions.py", "ext_handlers.py"}:
            assert "gtk4.pack_start" in text


def test_sidebar_layout_constructs_on_gtk4() -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk

    Adw.init()

    from ulauncher.ui import gtk4
    from ulauncher.ui.preferences.utils.sidebar_layout import SidebarItem, SidebarLayout

    layout = SidebarLayout()
    assert layout.listbox.get_first_child() is None
    icon = Gtk.Image.new_from_icon_name("image-missing")
    layout.set_items([SidebarItem(id="one", icon=icon, name="One")])
    rows = gtk4.list_children(layout.listbox)
    assert len(rows) == 1
    assert layout.listbox.get_first_child() is not None
