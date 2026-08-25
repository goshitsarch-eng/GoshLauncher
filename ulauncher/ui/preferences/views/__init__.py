from __future__ import annotations

from time import time
from typing import Any, Callable, TypeVar, cast

from gi.repository import Gtk

from ulauncher.ui import gtk4
from ulauncher.utils import scheduling

T = TypeVar("T", bound=Gtk.Widget)

# Shared constants
ICON_SIZE_S = 24
ICON_SIZE_M = 32
ICON_SIZE_L = 48
ICON_SIZE_XL = 64
SIDEBAR_WIDTH = 280
SPINNER_MIN_ANIMATION = 0.25


def get_window_for_widget(widget: Gtk.Widget) -> Gtk.Window | None:
    root = None
    get_root = getattr(widget, "get_root", None)
    if callable(get_root):
        root = get_root()
    if root is None:
        get_toplevel = getattr(widget, "get_toplevel", None)
        if callable(get_toplevel):
            root = get_toplevel()
    if root and isinstance(root, Gtk.Window):
        return root
    return None


def _in_destruction(widget: Any) -> bool:
    probe = getattr(widget, "in_destruction", None)
    return bool(probe()) if callable(probe) else False


def prefs_view_reload_action(toplevel: Any, widget: Any) -> str:
    """Return stop/skip/reload for a periodic prefs-view refresh.

    GTK 4 removed Gtk.Window.get_window(). An unmapped widget is not
    destroyed — Adw.PreferencesWindow hides stack pages that way.
    """
    if toplevel is None:
        return "stop"
    if _in_destruction(toplevel) or _in_destruction(widget):
        return "stop"
    mapped = False
    get_mapped = getattr(widget, "get_mapped", None)
    if callable(get_mapped):
        mapped = bool(get_mapped())
    native = None
    get_native = getattr(widget, "get_native", None)
    if callable(get_native):
        native = get_native()
    if mapped or native is not None:
        return "reload"
    return "skip"


def styled(widget: T, *class_names: str) -> T:
    for class_name in class_names:
        gtk4.add_css_class(widget, class_name)
    return widget


def start_spinner_button_animation(button: Gtk.Button) -> Callable[[], None]:
    """
    Starts the spinner animation for a button with a minimum animation duration
    Returns a function to stops the animation
    """
    start_time = time()
    gtk4.add_css_class(button, "spinner-button")
    button.set_sensitive(False)

    def do_stop_animation() -> None:
        gtk4.remove_css_class(button, "spinner-button")
        button.set_sensitive(True)

    def stop_animation() -> None:
        time_passed = time() - start_time
        timeout = max(0, SPINNER_MIN_ANIMATION - time_passed)
        scheduling.timer(timeout, do_stop_animation)

    return stop_animation


class BaseView(Gtk.Box):
    """Base class for preference views (for public methods)"""

    def save_changes(self) -> bool:
        """Save changes and return True if successful, False otherwise.

        This is a no-op implementation that views can override to handle Ctrl+S.
        """
        return False


class DataListBoxRow(Gtk.ListBoxRow):
    """A ListBox row that can store an id reference"""

    def __init__(self, identifier: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.id = identifier


class TextArea(Gtk.TextView):
    """A wrapper around Gtk.TextView that makes it easier to get and set the buffer"""

    def set_text(self, text: str) -> None:
        self.get_buffer().set_text(text)

    def get_text(self) -> str:
        buffer = self.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)


class DialogLauncher:
    def __init__(self, widget: Gtk.Widget) -> None:
        self.widget = widget

    def show(
        self,
        text: str,
        secondary_text: str,
        message_type: Gtk.MessageType | None = None,
        buttons: Gtk.ButtonsType | None = None,
    ) -> Gtk.ResponseType | None:
        dialog = Gtk.MessageDialog(
            transient_for=get_window_for_widget(self.widget),
            modal=True,
            message_type=message_type or Gtk.MessageType.INFO,
            buttons=buttons or Gtk.ButtonsType.OK,
            text=text,
            secondary_text=secondary_text,
        )
        response = cast("Gtk.ResponseType | None", gtk4.run_dialog(dialog))
        dialog.destroy()
        return response

    def show_question(self, text: str, secondary_text: str) -> Gtk.ResponseType:
        response = self.show(text, secondary_text, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO)
        return cast("Gtk.ResponseType", response)

    def show_error(self, text: str, secondary_text: str) -> None:
        self.show(text, secondary_text, Gtk.MessageType.ERROR)
