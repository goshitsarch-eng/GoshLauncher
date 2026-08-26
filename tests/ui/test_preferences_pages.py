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
    assert "Auto-resume" not in text
    assert "Gosh Is Launcher" in text
    assert "The primary screen" in text
    about_path = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "about.py"
    assert not about_path.exists()


def test_about_page_documents_goshos_keyboard() -> None:
    source = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "help.py"
    text = source.read_text()
    assert "Alt+Number/Letter" not in text
    assert "Jump to result by position" not in text
    assert "pack_start" not in text
    assert "Alt+1" in text
    assert "Ctrl+N / Ctrl+P" in text
    assert "Checking" in text
    assert "Ctrl+Space" in text
    assert "def build_help_page" not in text
    prefs = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "preferences" / "views" / "preferences.py"
    about_src = prefs.read_text().split("def _build_about_page")[1].split("def _bind_settings_follow")[0]
    assert "Gosh Is Launcher" in about_src
    assert "look_about_subtitle()" in about_src
    assert "GTK 4" in about_src
    assert "add_usage_groups" not in about_src
    assert "Version" not in about_src
    assert (
        "add_usage_groups(page)"
        in prefs.read_text().split("def _build_desktop_page")[1].split("def _build_web_search_page")[0]
    )

    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.ui.preferences.views.help import add_usage_groups

    page = Adw.PreferencesPage(title="Desktop")
    add_usage_groups(page)
    assert page.get_title() == "Desktop"


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
        assert view.pages["desktop"].get_title() == "Desktop"
        assert "Desktop" not in titles
    finally:
        view.unbind_settings()


def _action_rows(widget: object) -> list[tuple[str, str]]:
    from gi.repository import Adw

    from ulauncher.ui import gtk4

    rows: list[tuple[str, str]] = []
    if isinstance(widget, Adw.ActionRow):
        rows.append((str(widget.get_title()), str(widget.get_subtitle() or "")))
    for child in gtk4.list_children(widget):
        rows.extend(_action_rows(child))
    return rows


def test_about_page_matches_goshos_three_rows() -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.modes.launcher.looks import look_about_subtitle
    from ulauncher.ui.preferences.views.preferences import PreferencesView

    view = PreferencesView()
    try:
        about = view.pages["about"]
        rows = _action_rows(about)
        titles = [title for title, _subtitle in rows]
        assert titles[:3] == ["Gosh Is Launcher", "Looks", "GTK 4"]
        assert "Version" not in titles
        assert "Keyboard" not in titles
        assert "Prefixes" not in titles
        assert rows[0][1] == "A compact launcher with interchangeable looks."
        assert rows[1][1] == look_about_subtitle()
        assert "Walker" in rows[1][1]
        assert "COSMIC" in rows[1][1]
        desktop_titles = [title for title, _subtitle in _action_rows(view.pages["desktop"])]
        assert "Ctrl+Space" in desktop_titles
        assert "=" in desktop_titles
        assert "Spotlight-goshos" in desktop_titles
    finally:
        view.unbind_settings()


def test_preferences_window_lists_goshos_pages_before_desktop_extras() -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.ui.preferences.preferences_window import PreferencesWindow

    window = PreferencesWindow()
    try:
        assert window._page_order[:5] == ["Shortcut", "Appearance", "Features", "Web Search", "About"]
        assert window._page_order[5] == "Desktop"
        assert "Help" not in window._page_order
        assert "Shortcuts" in window._page_order
        assert "Extensions" in window._page_order
    finally:
        window._launcher_prefs.unbind_settings()


def test_prefs_window_default_size_matches_goshos() -> None:
    from ulauncher.ui.preferences.preferences_window import WINDOW_DEFAULT_HEIGHT, WINDOW_DEFAULT_WIDTH

    assert (WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT) == (680, 720)


def test_reset_look_restores_chrome_picking_same_look_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher.modes.launcher.looks import LOOKS, get_look
    from ulauncher.ui.preferences.views.preferences import PreferencesView
    from ulauncher.utils.settings import Settings

    settings = Settings()
    settings.update(
        {
            "look_id": "spotlight",
            "applied_look": "spotlight",
            "icon_size": 48,
            "enable_prefix_modes": False,
            "enable_command_run": False,
        }
    )
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))

    view = PreferencesView()
    try:
        assert view.settings is settings
        view._on_look_selected(view._look_combo)
        assert settings.icon_size == 48
        assert int(view._icon_spin.get_value_as_int()) == 48
        view._on_reset_look_clicked(view._icon_spin)
        assert settings.icon_size == get_look("spotlight")["look"]["icon_size"]
        assert settings.icon_size == 28
        assert int(view._icon_spin.get_value_as_int()) == 28
        assert view._command_switch.get_sensitive() is False
        settings.enable_prefix_modes = True
        view._sync_dependent_switches()
        assert view._command_switch.get_sensitive() is True
        settings.enable_prefix_modes = False
        view._sync_dependent_switches()
        assert view._command_switch.get_sensitive() is False
        pop = next(index for index, look in enumerate(LOOKS) if look["id"] == "popos")
        view._look_combo.set_selected(pop)
        assert settings.look_id == "popos"
        assert settings.icon_size == get_look("popos")["look"]["icon_size"]
        assert settings.popup_position == "top"
    finally:
        view.unbind_settings()


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


def test_desktop_page_credits_upstreams_with_the_version() -> None:
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()

    from ulauncher import version
    from ulauncher.ui import gtk4
    from ulauncher.ui.preferences.views.help import add_usage_groups

    page = Adw.PreferencesPage(title="Desktop")
    add_usage_groups(page)

    rows: list[str] = []
    descriptions: list[str] = []

    def walk(widget: object) -> None:
        if isinstance(widget, Adw.ActionRow):
            rows.append(str(widget.get_title()))
        if isinstance(widget, Adw.PreferencesGroup):
            descriptions.append(str(widget.get_description() or ""))
        for child in gtk4.list_children(widget):
            walk(child)

    walk(page)
    # GPL-3.0 5(a): a modified Ulauncher has to say so somewhere the user can see it
    assert "Ulauncher" in rows
    assert "Spotlight-goshos" in rows
    assert "GoshLauncher" in rows
    assert any(version in text and "GPL" in text for text in descriptions)
