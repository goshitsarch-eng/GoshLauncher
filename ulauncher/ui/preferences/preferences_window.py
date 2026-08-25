from __future__ import annotations

from pathlib import Path
from typing import Any

from gi.repository import Adw, Gdk, Gtk

from ulauncher import paths
from ulauncher.ui.gtk4 import add_provider_to_display, load_css_provider
from ulauncher.ui.helpers.system_theme import SystemThemeWatcher
from ulauncher.ui.preferences.adw_rows import wrap_custom_view
from ulauncher.ui.preferences.page_names import GOSHOS_PAGE_IDS, normalize_prefs_page
from ulauncher.ui.preferences.views.extensions import ExtensionsView
from ulauncher.ui.preferences.views.help import HelpView
from ulauncher.ui.preferences.views.preferences import PreferencesView
from ulauncher.ui.preferences.views.shortcuts import ShortcutsView

WINDOW_DEFAULT_WIDTH = 840
WINDOW_DEFAULT_HEIGHT = 720

_CUSTOM_PAGES = (
    ("shortcuts", "Shortcuts", "input-keyboard-symbolic", ShortcutsView),
    ("extensions", "Extensions", "application-x-addon-symbolic", ExtensionsView),
    ("help", "Help", "help-browser-symbolic", HelpView),
)


class PreferencesWindow(Adw.PreferencesWindow):
    """Adwaita preferences window with Spotlight-goshos pages plus desktop extras."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Preferences", **kwargs)
        self.set_default_size(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.set_search_enabled(True)

        self.views: dict[str, Any] = {}
        self._pages: dict[str, Adw.PreferencesPage] = {}
        self._theme_watcher: SystemThemeWatcher | None = None

        self._watch_system_theme()
        self._create_pages()
        self._setup_keybindings()
        self._setup_custom_styling()
        self.connect("close-request", self._on_close_request)

    def _create_pages(self) -> None:
        self._launcher_prefs = PreferencesView()
        self._pages.update(self._launcher_prefs.pages)
        for key in GOSHOS_PAGE_IDS:
            if key == "about":
                continue
            self.add(self._pages[key])
        for key, title, icon_name, view_class in _CUSTOM_PAGES:
            view = view_class()
            page = wrap_custom_view(title, icon_name, view)
            self._pages[key] = page
            self.views[key] = view
            self.add(page)
        self.add(self._pages["about"])

    def present(self, view: str | None = None) -> None:  # type: ignore[override]
        self.show(view)
        super().present()

    def show(self, view: str | None = None) -> None:  # type: ignore[override]
        key = normalize_prefs_page(view)
        if key:
            page = self._pages.get(key)
            if page is not None:
                self.set_visible_page(page)
        self.set_visible(True)

    def _setup_keybindings(self) -> None:
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_press)
        self.add_controller(keys)

    def _on_key_press(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not ctrl or Gdk.keyval_name(keyval) != "s":
            return False
        page = self.get_visible_page()
        for key, candidate in self._pages.items():
            if candidate is page:
                view = self.views.get(key)
                save = getattr(view, "save_changes", None)
                if callable(save):
                    return bool(save())
                return False
        return False

    def _setup_custom_styling(self) -> None:
        css = Path(f"{paths.ASSETS}/preferences.css").read_text()
        provider = load_css_provider(css)
        add_provider_to_display(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _watch_system_theme(self) -> None:
        self._theme_watcher = SystemThemeWatcher(self._apply_system_theme)
        self._theme_watcher.start()

    def _apply_system_theme(self, prefers_dark: bool) -> None:
        if gtk_settings := self.get_settings():
            gtk_settings.props.gtk_application_prefer_dark_theme = prefers_dark

    def _on_close_request(self, *_args: Any) -> bool:
        if self._theme_watcher:
            self._theme_watcher.disconnect()
        self._launcher_prefs.unbind_settings()
        return False
