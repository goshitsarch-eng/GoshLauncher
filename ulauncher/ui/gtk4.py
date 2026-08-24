"""GTK4 helpers that replace GTK3 Container APIs used across the UI."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterator

from gi.repository import Gdk, GLib, Gtk


def pack_start(box: Gtk.Box, child: Gtk.Widget, expand: bool = True, fill: bool = True, padding: int = 0) -> None:
    """GTK3 Box.pack_start equivalent."""
    _pack(box, child, expand, fill, padding, start=True)


def pack_end(box: Gtk.Box, child: Gtk.Widget, expand: bool = True, fill: bool = True, padding: int = 0) -> None:
    """GTK3 Box.pack_end equivalent. Appends so the child sits at the end of the box."""
    _pack(box, child, expand, fill, padding, start=False)


def _pack(box: Gtk.Box, child: Gtk.Widget, expand: bool, fill: bool, padding: int, start: bool) -> None:
    vertical = box.get_orientation() == Gtk.Orientation.VERTICAL
    if vertical:
        child.set_vexpand(expand)
        if fill:
            child.set_valign(Gtk.Align.FILL)
        elif not expand:
            child.set_valign(Gtk.Align.START if start else Gtk.Align.END)
        if padding:
            child.set_margin_top(child.get_margin_top() + padding)
            child.set_margin_bottom(child.get_margin_bottom() + padding)
    else:
        child.set_hexpand(expand)
        if fill:
            child.set_halign(Gtk.Align.FILL)
        elif not expand:
            child.set_halign(Gtk.Align.START if start else Gtk.Align.END)
        if padding:
            child.set_margin_start(child.get_margin_start() + padding)
            child.set_margin_end(child.get_margin_end() + padding)
    if start:
        box.append(child)
        return
    box.append(child)


def add_child(parent: Gtk.Widget, child: Gtk.Widget) -> None:
    """GTK3 Container.add equivalent for the widgets this UI uses."""
    if isinstance(parent, Gtk.Box):
        parent.append(child)
        return
    setter = getattr(parent, "set_child", None)
    if callable(setter):
        setter(child)
        return
    append = getattr(parent, "append", None)
    if callable(append):
        append(child)
        return
    msg = f"Cannot add a child to {type(parent).__name__}"
    raise TypeError(msg)


def iter_children(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    get_first = getattr(widget, "get_first_child", None)
    if not callable(get_first):
        return
    child = get_first()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def list_children(widget: Gtk.Widget) -> list[Gtk.Widget]:
    return list(iter_children(widget))


def remove_all_children(widget: Gtk.Widget) -> None:
    for child in list_children(widget):
        widget.remove(child)


def show_all(widget: Gtk.Widget) -> None:
    widget.set_visible(True)
    for child in iter_children(widget):
        show_all(child)


def add_css_class(widget: Gtk.Widget, class_name: str) -> None:
    widget.add_css_class(class_name)


def remove_css_class(widget: Gtk.Widget, class_name: str) -> None:
    widget.remove_css_class(class_name)


def load_css_provider(css: str) -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    return provider


def add_provider_to_display(provider: Gtk.CssProvider, priority: int = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION) -> None:
    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(display, provider, priority)


def add_provider_to_widget(widget: Gtk.Widget, provider: Gtk.CssProvider) -> None:
    widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    for child in iter_children(widget):
        add_provider_to_widget(child, provider)


def clipboard_set_text(text: str) -> None:
    display = Gdk.Display.get_default()
    if not display:
        return
    clipboard = display.get_clipboard()
    clipboard.set(text)
    store_async = getattr(clipboard, "store_async", None)
    if callable(store_async):
        store_async(0, None, None, None)


def measure_height_for_width(widget: Gtk.Widget, width: int) -> tuple[int, int]:
    """GTK3 get_preferred_height_for_width equivalent using GTK4 measure()."""
    min_h, nat_h, _min_b, _nat_b = widget.measure(Gtk.Orientation.VERTICAL, width)
    return min_h, nat_h


def _dialog_run(self: Gtk.Dialog, *_args: Any, **_kwargs: Any) -> int:
    """GTK3 Dialog.run() using a nested main loop (Ubuntu 22.04 GTK 4.6 has no run())."""
    loop = GLib.MainLoop()
    result = {"id": int(Gtk.ResponseType.CLOSE)}

    def on_response(_dialog: Gtk.Dialog, response_id: int) -> None:
        result["id"] = int(response_id)
        loop.quit()

    handler = self.connect("response", on_response)
    self.set_modal(True)
    self.present()
    loop.run()
    self.disconnect(handler)
    return result["id"]


def install_compat() -> None:
    """Monkey-patch a few GTK3 names so preferences views keep compiling on GTK 4.6."""
    if not hasattr(Gtk.Box, "pack_start"):
        Gtk.Box.pack_start = lambda self, child, expand=True, fill=True, padding=0: pack_start(
            self, child, expand, fill, padding
        )
        Gtk.Box.pack_end = lambda self, child, expand=True, fill=True, padding=0: pack_end(
            self, child, expand, fill, padding
        )
    if not hasattr(Gtk.Box, "add"):
        Gtk.Box.add = lambda self, child: self.append(child)
    for cls_name in (
        "Window",
        "ApplicationWindow",
        "ScrolledWindow",
        "Frame",
        "Viewport",
        "Revealer",
        "Expander",
        "ListBox",
        "ListBoxRow",
        "Overlay",
    ):
        cls = getattr(Gtk, cls_name, None)
        if cls is not None and not hasattr(cls, "add"):
            cls.add = lambda self, child: add_child(self, child)
    if hasattr(Gtk, "ListBox") and not hasattr(Gtk.ListBox, "add"):
        Gtk.ListBox.add = lambda self, child: self.append(child)
    if not hasattr(Gtk.Widget, "show_all"):
        Gtk.Widget.show_all = show_all
    if not hasattr(Gtk.Widget, "get_children"):
        Gtk.Widget.get_children = list_children
    if not hasattr(Gtk.Widget, "get_toplevel"):
        Gtk.Widget.get_toplevel = lambda self: self.get_root()
    if hasattr(Gtk, "HeaderBar"):
        if not hasattr(Gtk.HeaderBar, "set_show_close_button"):
            Gtk.HeaderBar.set_show_close_button = lambda self, value: self.set_show_title_buttons(bool(value))
        if not hasattr(Gtk.HeaderBar, "set_custom_title"):
            Gtk.HeaderBar.set_custom_title = lambda self, widget: self.set_title_widget(widget)
    if not hasattr(Gtk.StyleContext, "add_provider_for_screen"):
        Gtk.StyleContext.add_provider_for_screen = lambda _screen, provider, priority: add_provider_to_display(
            provider, priority
        )
    if hasattr(Gtk, "Dialog") and not hasattr(Gtk.Dialog, "run"):
        Gtk.Dialog.run = _dialog_run
    if not hasattr(Gtk, "DialogFlags"):
        Gtk.DialogFlags = SimpleNamespace(MODAL=1, DESTROY_WITH_PARENT=2)
    if not hasattr(Gdk, "Screen"):
        Gdk.Screen = SimpleNamespace(get_default=Gdk.Display.get_default)
    if not hasattr(Gtk, "Menu"):
        Gtk.Menu = None
    if not hasattr(Gtk, "EventBox"):
        Gtk.EventBox = Gtk.Box
    if not hasattr(Gtk, "WindowPosition"):
        Gtk.WindowPosition = SimpleNamespace(NONE=0, CENTER=1, MOUSE=2, CENTER_ALWAYS=3, CENTER_ON_PARENT=4)
    if not hasattr(Gtk.Widget, "set_margin"):

        def _set_margin(self: Gtk.Widget, value: int) -> None:
            self.set_margin_top(value)
            self.set_margin_bottom(value)
            self.set_margin_start(value)
            self.set_margin_end(value)

        Gtk.Widget.set_margin = _set_margin
    if not hasattr(Gtk.Widget, "set_margin_left"):
        Gtk.Widget.set_margin_left = lambda self, value: self.set_margin_start(value)
        Gtk.Widget.set_margin_right = lambda self, value: self.set_margin_end(value)
    if not hasattr(Gtk, "IconSize"):
        Gtk.IconSize = SimpleNamespace(
            INVALID=0, MENU=1, SMALL_TOOLBAR=2, LARGE_TOOLBAR=3, BUTTON=4, DND=5, DIALOG=6, INHERIT=0
        )
    if not hasattr(Gtk, "ShadowType"):
        Gtk.ShadowType = SimpleNamespace(NONE=0, IN=1, OUT=2, ETCHED_IN=3, ETCHED_OUT=4)
    if not hasattr(Gtk, "STOCK_CANCEL"):
        Gtk.STOCK_CANCEL = "_Cancel"
        Gtk.STOCK_OK = "_OK"
    if not hasattr(Gtk.Button, "set_image"):
        Gtk.Button.set_image = lambda self, image: self.set_child(image)
    if not hasattr(Gtk.Image, "new_from_surface"):
        Gtk.Image.new_from_surface = staticmethod(lambda paintable: Gtk.Image(paintable=paintable))
    if hasattr(Gtk, "FileChooserDialog") and not hasattr(Gtk.FileChooserDialog, "get_filename"):

        def _get_filename(self: Gtk.FileChooserDialog) -> str | None:
            file = self.get_file()
            return file.get_path() if file is not None else None

        Gtk.FileChooserDialog.get_filename = _get_filename
    # GTK4 Image.new_from_icon_name(name) only; GTK3 passed a size as the second argument.
    if not getattr(Gtk.Image, "_ulauncher_icon_name_compat", False):
        _image_from_icon = Gtk.Image.new_from_icon_name

        def _new_from_icon_name(icon_name: str, _size: object = None) -> Gtk.Image:
            return _image_from_icon(icon_name)

        Gtk.Image.new_from_icon_name = staticmethod(_new_from_icon_name)  # type: ignore[assignment]
        Gtk.Image._ulauncher_icon_name_compat = True
