"""Paint a look's CSS tree so tests can sample GTK4 pixels."""

from __future__ import annotations

from ulauncher.ui.gtk4 import load_css_provider
from ulauncher.ui.helpers.theme import launcher_popup_css

_state: dict[str, bool] = {"ready": False}


def ensure_look_css() -> None:
    if _state["ready"]:
        return
    from gi.repository import Adw, Gdk, Gtk

    Adw.init()
    provider = load_css_provider(launcher_popup_css())
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    _state["ready"] = True


def display_available() -> bool:
    from gi.repository import Gdk

    ensure_look_css()
    return Gdk.Display.get_default() is not None


def pump(times: int = 20) -> None:
    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    for _ in range(times):
        ctx.iteration(False)


def build_look_tree(look_id: str) -> tuple[object, object, object, object]:
    from gi.repository import Gtk

    ensure_look_css()
    win = Gtk.Window()
    win.set_decorated(False)
    win.set_default_size(480, 280)
    win.add_css_class("gosh-popup")

    app = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    app.add_css_class("app")
    app.add_css_class(f"gosh-theme-{look_id}")
    app.set_hexpand(True)
    app.set_vexpand(True)

    prompt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    prompt.add_css_class("prompt")
    prompt.set_size_request(-1, 56)
    entry = Gtk.Entry()
    entry.add_css_class("input")
    entry.set_hexpand(True)
    prompt.append(entry)

    result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    result_box.add_css_class("result-box")
    selected = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    selected.add_css_class("item-box")
    selected.add_css_class("selected")
    selected.set_size_request(-1, 44)
    row_label = Gtk.Label(label="Result")
    row_label.set_hexpand(True)
    row_label.set_xalign(0.0)
    selected.append(row_label)
    result_box.append(selected)

    app.append(prompt)
    app.append(result_box)
    win.set_child(app)
    return win, app, prompt, selected


def widget_rgb(widget: object, x: int, y: int) -> tuple[int, int, int]:
    from gi.repository import Graphene, Gtk

    native = widget.get_native()
    renderer = native.get_renderer() if native is not None else None
    if renderer is None:
        msg = "look widget has no GSK renderer"
        raise RuntimeError(msg)
    width = max(int(widget.get_width()), 1)
    height = max(int(widget.get_height()), 1)
    paintable = Gtk.WidgetPaintable.new(widget)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()
    if node is None:
        msg = "look widget produced no render node"
        raise RuntimeError(msg)
    viewport = Graphene.Rect()
    viewport.init(0, 0, float(width), float(height))
    texture = renderer.render_texture(node, viewport)
    from gi.repository import Gdk

    pixbuf = Gdk.pixbuf_get_from_texture(texture)
    if pixbuf is None:
        msg = "could not read look texture"
        raise RuntimeError(msg)
    rowstride = pixbuf.get_rowstride()
    channels = pixbuf.get_n_channels()
    pixels = pixbuf.get_pixels()
    px = min(max(x, 0), pixbuf.get_width() - 1)
    py = min(max(y, 0), pixbuf.get_height() - 1)
    idx = py * rowstride + px * channels
    return pixels[idx], pixels[idx + 1], pixels[idx + 2]


def sample_look(look_id: str) -> dict[str, tuple[int, int, int]]:
    from gi.repository import GLib

    win, app, prompt, selected = build_look_tree(look_id)
    mapped = {"ok": False}

    def on_map(*_args: object) -> None:
        mapped["ok"] = True

    win.connect("map", on_map)
    win.present()
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if mapped["ok"] and prompt.get_width() > 40 and selected.get_width() > 40 and selected.get_height() > 10:
            break
    if prompt.get_width() <= 40 or selected.get_width() <= 40:
        win.close()
        pump(8)
        msg = (
            f"look {look_id} did not allocate "
            f"(prompt {prompt.get_width()}x{prompt.get_height()}, "
            f"selected {selected.get_width()}x{selected.get_height()})"
        )
        raise RuntimeError(msg)
    panel = prompt if look_id == "spotlight" else app
    panel_rgb = widget_rgb(panel, 24, 16)
    # Label text sits on the start edge; sample trailing padding for the row fill.
    selected_x = max(int(selected.get_width()) - 16, 4)
    selected_y = max(int(selected.get_height()) // 2, 4)
    selected_rgb = widget_rgb(selected, selected_x, selected_y)
    win.close()
    pump(8)
    return {"panel": panel_rgb, "selected": selected_rgb}


def css_parsing_errors(css: str) -> list[str]:
    from gi.repository import Gtk

    errors: list[str] = []

    def on_error(_provider: object, _section: object, error: object) -> None:
        errors.append(getattr(error, "message", None) or str(error))

    provider = Gtk.CssProvider()
    provider.connect("parsing-error", on_error)
    provider.load_from_data(css.encode())
    return errors
