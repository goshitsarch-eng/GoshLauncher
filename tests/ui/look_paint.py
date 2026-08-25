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


def widget_pixbuf(widget: object) -> object:
    from gi.repository import Gdk, Graphene, Gtk

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
    pixbuf = Gdk.pixbuf_get_from_texture(texture)
    if pixbuf is None:
        msg = "could not read look texture"
        raise RuntimeError(msg)
    return pixbuf


def widget_rgb(widget: object, x: int, y: int) -> tuple[int, int, int]:
    pixbuf = widget_pixbuf(widget)
    rowstride = pixbuf.get_rowstride()
    channels = pixbuf.get_n_channels()
    pixels = pixbuf.get_pixels()
    px = min(max(x, 0), pixbuf.get_width() - 1)
    py = min(max(y, 0), pixbuf.get_height() - 1)
    idx = py * rowstride + px * channels
    return pixels[idx], pixels[idx + 1], pixels[idx + 2]


def widget_pixbuf_retry(widget: object, tries: int = 24) -> object:
    last: Exception | None = None
    for _ in range(tries):
        try:
            return widget_pixbuf(widget)
        except RuntimeError as exc:
            last = exc
            pump(4)
    assert last is not None
    raise last


def widget_rgb_retry(widget: object, x: int, y: int, tries: int = 24) -> tuple[int, int, int]:
    last: Exception | None = None
    for _ in range(tries):
        try:
            return widget_rgb(widget, x, y)
        except RuntimeError as exc:
            last = exc
            pump(4)
    assert last is not None
    raise last


def _nearest_colored_rgb(pixbuf: object, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    """Closest non-black pixel to ``expected``. Placeholder glyphs sit on a transparent snapshot."""
    rowstride = pixbuf.get_rowstride()
    channels = pixbuf.get_n_channels()
    pixels = pixbuf.get_pixels()
    width = pixbuf.get_width()
    height = pixbuf.get_height()
    best: tuple[int, int, int] | None = None
    best_d = 10**9
    y0 = max(height // 2 - 2, 0)
    y1 = min(height // 2 + 3, height)
    for py in range(y0, y1):
        for px in range(width):
            idx = py * rowstride + px * channels
            rgb = (pixels[idx], pixels[idx + 1], pixels[idx + 2])
            if rgb == (0, 0, 0):
                continue
            delta = abs(rgb[0] - expected[0]) + abs(rgb[1] - expected[1]) + abs(rgb[2] - expected[2])
            if delta < best_d:
                best_d = delta
                best = rgb
    if best is None:
        msg = "placeholder produced no colored pixels"
        raise RuntimeError(msg)
    return best


def _placeholder_label(entry: object) -> object:
    from gi.repository import Gtk

    from ulauncher.ui import gtk4

    for child in gtk4.iter_children(entry):
        if isinstance(child, Gtk.Label):
            return child
        for nested in gtk4.iter_children(child):
            if isinstance(nested, Gtk.Label):
                return nested
    return entry


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


_popup: dict[str, object] = {}


def _skip_backdrop(_self: object) -> None:
    return


def _skip_unredirect(_self: object, _want_held: bool = False) -> None:
    return


def _skip_watch(_self: object) -> None:
    return


def _skip_grab(_self: object, _grab: bool) -> None:
    return


def patch_window_host(stack: object) -> None:
    """Skip compositor, tray, and session watches that hang headless GTK tests."""
    from unittest.mock import patch

    from ulauncher.ui.ulauncher_window import UlauncherWindow

    enter = stack.enter_context  # type: ignore[attr-defined]
    enter(patch.object(UlauncherWindow, "_show_backdrop", _skip_backdrop))
    enter(patch.object(UlauncherWindow, "_apply_unredirect", _skip_unredirect))
    enter(patch.object(UlauncherWindow, "_start_live_search", _skip_watch))
    enter(patch.object(UlauncherWindow, "_start_osk_watch", _skip_watch))
    enter(patch.object(UlauncherWindow, "_start_session_watch", _skip_watch))
    enter(patch.object(UlauncherWindow, "_start_limits_timer", _skip_watch))
    enter(patch.object(UlauncherWindow, "toggle_grab_pointer_device", _skip_grab))


def wait_popup_styled(win: object) -> None:
    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 4_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if win.get_opacity() == 1 and win.prompt.get_width() > 40:  # type: ignore[attr-defined]
            pump(24)
            return
    opacity = win.get_opacity()  # type: ignore[attr-defined]
    prompt = win.prompt  # type: ignore[attr-defined]
    msg = f"popup window did not style (opacity {opacity}, prompt {prompt.get_width()}x{prompt.get_height()})"
    raise RuntimeError(msg)


def _find_css_class(widget: object, class_name: str) -> object | None:
    from ulauncher.ui import gtk4

    has_class = getattr(widget, "has_css_class", None)
    if callable(has_class) and has_class(class_name):
        return widget
    for child in gtk4.iter_children(widget):
        found = _find_css_class(child, class_name)
        if found is not None:
            return found
    return None


def restyle_popup(win: object, look_id: str) -> None:
    from ulauncher.modes.launcher.looks import chrome_from_settings

    win.settings.look_id = look_id  # type: ignore[attr-defined]
    win._chrome = chrome_from_settings(win.settings)  # type: ignore[attr-defined]
    win._apply_look_classes()  # type: ignore[attr-defined]
    win._sync_search_entry()  # type: ignore[attr-defined]
    win.apply_theme()  # type: ignore[attr-defined]
    win.position_window()  # type: ignore[attr-defined]
    pump(12)


def _fill_selected_result(win: object) -> object:
    from ulauncher.internals.query import Query
    from ulauncher.internals.result import Result
    from ulauncher.internals.results_update import results_update

    win.show_results(  # type: ignore[attr-defined]
        results_update(
            [
                Result(
                    name="Result",
                    highlightable=True,
                    compact=True,
                    actions={"open": {"name": "Open"}},
                )
            ],
            Query("pixel", None),
        )
    )
    pump(16)
    widgets = getattr(win.results_view, "_widgets", [])  # type: ignore[attr-defined]
    if not widgets:
        msg = "popup window has no result widgets"
        raise RuntimeError(msg)
    selected = widgets[0].item_box
    if selected.get_width() <= 0:
        selected = _find_css_class(win.theme_root, "selected")  # type: ignore[attr-defined]
    if selected is None:
        msg = "popup window has no selected result row"
        raise RuntimeError(msg)
    return selected


def open_popup_window() -> object:
    if "win" in _popup:
        return _popup["win"]

    from contextlib import ExitStack

    from gi.repository import Adw, Gio

    from ulauncher.ui.ulauncher_window import UlauncherWindow

    ensure_look_css()
    Adw.init()

    class LookPixelApp(Adw.Application):
        query = ""

        def window_ready(self) -> None:
            return

        def show_preferences(self, *_args: object, **_kwargs: object) -> None:
            return

        def query_changed(self, query_str: str) -> None:
            self.query = (query_str or "").lstrip()

        def request_close(self, save_query: bool = False) -> None:  # noqa: ARG002
            return

        def close_launcher(self, *_args: object, **_kwargs: object) -> None:
            return

        def set_query(self, value: str, update_input: bool = True) -> None:
            self.query = value
            if not update_input:
                return

        def activate_result(self, *_args: object, **_kwargs: object) -> None:
            return

        def handle_backspace(self, _query_str: str) -> bool:
            return False

    app = LookPixelApp(application_id="io.ulauncher.LookPixelTest", flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register()
    stack = ExitStack()
    patch_window_host(stack)
    win = UlauncherWindow(application=app)
    try:
        wait_popup_styled(win)
    except RuntimeError:
        win.close()
        stack.close()
        pump(8)
        raise
    _popup["app"] = app
    _popup["win"] = win
    _popup["stack"] = stack
    return win


def close_popup_window() -> None:
    win = _popup.pop("win", None)
    stack = _popup.pop("stack", None)
    _popup.pop("app", None)
    closer = getattr(win, "close", None)
    if callable(closer):
        closer()
    closer = getattr(stack, "close", None)
    if callable(closer):
        closer()
    pump(8)


def sample_popup_look(look_id: str) -> dict[str, tuple[int, int, int]]:
    from gi.repository import GLib

    win = open_popup_window()
    restyle_popup(win, look_id)
    selected = _fill_selected_result(win)
    prompt = win.prompt  # type: ignore[attr-defined]
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if prompt.get_width() > 40 and selected.get_width() > 40 and selected.get_height() > 10:
            break
    if prompt.get_width() <= 40 or selected.get_width() <= 40:
        msg = (
            f"popup look {look_id} did not allocate "
            f"(prompt {prompt.get_width()}x{prompt.get_height()}, "
            f"selected {selected.get_width()}x{selected.get_height()})"
        )
        raise RuntimeError(msg)
    panel = prompt if look_id == "spotlight" else win.theme_root  # type: ignore[attr-defined]
    # Top-center sits in look padding, past rounded-corner border and the search icon.
    panel_x = max(int(panel.get_width()) // 2, 8)
    panel_rgb = widget_rgb_retry(panel, panel_x, 2)
    selected_x = max(int(selected.get_width()) - 16, 4)
    selected_y = max(int(selected.get_height()) // 2, 4)
    selected_rgb = widget_rgb_retry(selected, selected_x, selected_y)
    return {"panel": panel_rgb, "selected": selected_rgb}


def _entry_in_prompt(prompt: object) -> object | None:
    from gi.repository import Gtk

    from ulauncher.ui import gtk4

    for child in gtk4.iter_children(prompt):
        if isinstance(child, Gtk.Entry) or (hasattr(child, "has_css_class") and child.has_css_class("input")):
            return child
    return None


def _sample_selected_entry(app: object, entry: object) -> tuple[int, int, int]:
    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    rgb: tuple[int, int, int] | None = None
    last_error: Exception | None = None
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        sample_x = 24
        sample_y = max(int(entry.get_height()) // 2, 4)
        ok, bounds = entry.compute_bounds(app)
        if ok and bounds is not None:
            sample_x = int(bounds.get_x() + max(bounds.get_width() * 0.1, 8))
            sample_y = int(bounds.get_y() + max(bounds.get_height() / 2, 4))
        try:
            sampled = widget_rgb(app, sample_x, sample_y)
        except RuntimeError as exc:
            last_error = exc
            continue
        rgb = sampled
        if sampled != (0, 0, 0):
            return sampled
    if rgb is not None:
        return rgb
    if last_error is not None:
        raise last_error
    msg = "entry selection produced no pixels"
    raise RuntimeError(msg)


def sample_entry_selection(look_id: str) -> tuple[int, int, int]:
    """Paint a selected query so GTK4 ``selection`` CSS can be sampled."""
    from gi.repository import GLib

    win, app, prompt, _selected = build_look_tree(look_id)
    entry = _entry_in_prompt(prompt)
    if entry is None:
        win.close()
        pump(8)
        msg = f"look {look_id} has no search entry"
        raise RuntimeError(msg)
    mapped = {"ok": False}

    def on_map(*_args: object) -> None:
        mapped["ok"] = True

    win.connect("map", on_map)
    win.present()
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if mapped["ok"] and entry.get_width() > 40 and entry.get_height() > 8:
            break
    entry.grab_focus()
    entry.set_text("MMMMMMMM")
    entry.select_region(0, -1)
    try:
        return _sample_selected_entry(app, entry)
    finally:
        win.close()
        pump(8)


def sample_placeholder(look_id: str, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    """Paint an empty search hint so look ``text.placeholder`` CSS can be sampled."""
    from gi.repository import GLib

    from ulauncher.modes.launcher.looks import get_look

    win, _app, prompt, _selected = build_look_tree(look_id)
    entry = _entry_in_prompt(prompt)
    if entry is None:
        win.close()
        pump(8)
        msg = f"look {look_id} has no search entry"
        raise RuntimeError(msg)
    entry.set_placeholder_text(get_look(look_id)["hint"])
    entry.set_text("")
    mapped = {"ok": False}

    def on_map(*_args: object) -> None:
        mapped["ok"] = True

    win.connect("map", on_map)
    win.present()
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if mapped["ok"] and entry.get_width() > 40 and entry.get_height() > 8:
            break
    try:
        target = _placeholder_label(entry)
        pixbuf = widget_pixbuf_retry(target)
        return _nearest_colored_rgb(pixbuf, expected)
    finally:
        win.close()
        pump(8)


def sample_popup_placeholder(look_id: str, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    """Sample the live popup's empty-entry hint after restyling to ``look_id``."""
    from gi.repository import GLib

    win = open_popup_window()
    restyle_popup(win, look_id)
    entry = win.prompt_input  # type: ignore[attr-defined]
    entry.set_text("")
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + 2_000_000
    while GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
        if entry.get_width() > 40 and entry.get_height() > 8 and not entry.get_text():
            pump(8)
            break
    target = _placeholder_label(entry)
    pixbuf = widget_pixbuf_retry(target)
    return _nearest_colored_rgb(pixbuf, expected)
