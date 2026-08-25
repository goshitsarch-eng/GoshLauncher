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
