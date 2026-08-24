from __future__ import annotations

from pathlib import Path
from typing import Any

from gi.repository import Adw, Gdk, Gtk

from ulauncher import paths
from ulauncher.ui.gtk4 import add_css_class, add_provider_to_display, load_css_provider
from ulauncher.ui.helpers.system_theme import SystemThemeWatcher
from ulauncher.ui.preferences.views import BaseView, styled
from ulauncher.ui.preferences.views.about import AboutView
from ulauncher.ui.preferences.views.extensions import ExtensionsView
from ulauncher.ui.preferences.views.help import HelpView
from ulauncher.ui.preferences.views.preferences import PreferencesView
from ulauncher.ui.preferences.views.shortcuts import ShortcutsView

VIEW_CONFIG: list[tuple[str, type[BaseView]]] = [
    ("Preferences", PreferencesView),
    ("Shortcuts", ShortcutsView),
    ("Extensions", ExtensionsView),
    ("Help", HelpView),
    ("About", AboutView),
]
WINDOW_DEFAULT_WIDTH = 1000
WINDOW_DEFAULT_HEIGHT = 600


class PreferencesWindow(Adw.ApplicationWindow):
    """Adwaita preferences window with a stack of settings pages."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Ulauncher Preferences", resizable=True, **kwargs)

        self.set_default_size(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.views: dict[str, BaseView] = {}
        self._theme_watcher: SystemThemeWatcher | None = None

        self._watch_system_theme()
        self._create_ui()
        self._setup_keybindings()
        self.connect("close-request", self._on_close_request)

    def _create_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(main_box)

        self.stack: Gtk.Stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=200
        )
        main_box.append(self.stack)
        self.stack.set_vexpand(True)

        self._create_headerbar()

        for name, view_class in VIEW_CONFIG:
            view = view_class()
            self._add_view(view, name)

        self._setup_custom_styling()

    def _create_headerbar(self) -> None:
        header_bar = Adw.HeaderBar()
        add_css_class(header_bar, "preferences-header")

        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        stack_switcher.set_halign(Gtk.Align.CENTER)
        stack_switcher.set_hexpand(False)
        add_css_class(stack_switcher, "preferences-nav")

        header_bar.set_title_widget(stack_switcher)
        self.set_titlebar(header_bar)

    def _add_view(self, view: BaseView, label_text: str) -> None:
        view_bg = styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), "view-container")
        view.set_hexpand(True)
        view.set_vexpand(True)
        view_bg.append(view)
        page_name = label_text.lower()
        self.stack.add_titled(view_bg, page_name, label_text)
        self.views[page_name] = view

    def present(self, view: str | None = None) -> None:  # type: ignore[override]
        self.show(view)
        super().present()

    def show(self, view: str | None = None) -> None:  # type: ignore[override]
        if view:
            page_name = view.lower()
            if self.stack.get_child_by_name(page_name):
                self.stack.set_visible_child_name(page_name)
        self.set_visible(True)

    def _setup_keybindings(self) -> None:
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_press)
        self.add_controller(keys)

    def _on_key_press(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        page_name = self.stack.get_visible_child_name()
        if not page_name:
            return False
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and Gdk.keyval_name(keyval) == "s":
            return self.views[page_name].save_changes()
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
        view = self.views.get("preferences")
        unbind = getattr(view, "unbind_settings", None)
        if callable(unbind):
            unbind()
        return False
