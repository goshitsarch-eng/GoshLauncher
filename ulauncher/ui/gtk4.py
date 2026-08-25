"""GTK4 helpers that replace GTK3 Container APIs used across the UI."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from gi.repository import Gdk, GLib, Gtk

logger = logging.getLogger(__name__)


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


def image_from_paintable(paintable: Any) -> Gtk.Image:
    """GTK4 Image from a Gdk.Paintable (GTK3 used Image.new_from_surface)."""
    return Gtk.Image(paintable=paintable)


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
    provider.connect("parsing-error", _on_css_parsing_error)
    provider.load_from_data(css.encode())
    return provider


def _on_css_parsing_error(_provider: Gtk.CssProvider, _section: object, error: object) -> None:
    message = getattr(error, "message", None) or str(error)
    logger.warning("GTK CSS parser: %s", message)


def add_provider_to_display(provider: Gtk.CssProvider, priority: int = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION) -> None:
    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(display, provider, priority)


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


def run_dialog(dialog: Gtk.Dialog) -> int:
    """Block until a GTK4 dialog emits ``response`` (GTK 4.6 has no Dialog.run())."""
    return _dialog_run(dialog)


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
