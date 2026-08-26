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


def _gtk_version() -> str:
    from gi.repository import Gtk

    return f"{Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}"


def _native_renderer(widget: object) -> object | None:
    native = widget.get_native()
    if native is None:
        return None
    surface = native.get_surface()
    if surface is not None:
        queue = getattr(surface, "queue_render", None)
        if callable(queue):
            queue()
    return native.get_renderer()


def widget_pixbuf(widget: object) -> object:
    from gi.repository import Gdk, Graphene, Gtk

    renderer = _native_renderer(widget)
    if renderer is None:
        msg = f"look widget has no GSK renderer (GTK {_gtk_version()})"
        raise RuntimeError(msg)
    width = max(int(widget.get_width()), 1)
    height = max(int(widget.get_height()), 1)
    paintable = Gtk.WidgetPaintable.new(widget)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()
    if node is None:
        native = widget.get_native()
        if native is not None and native is not widget:
            native_w = max(int(native.get_width()), width)
            native_h = max(int(native.get_height()), height)
            native_paint = Gtk.WidgetPaintable.new(native)
            native_snap = Gtk.Snapshot()
            native_paint.snapshot(native_snap, native_w, native_h)
            node = native_snap.to_node()
            width, height = native_w, native_h
    if node is None:
        msg = f"look widget produced no render node (GTK {_gtk_version()})"
        raise RuntimeError(msg)
    viewport = Graphene.Rect()
    viewport.init(0, 0, float(width), float(height))
    texture = renderer.render_texture(node, viewport)
    pixbuf = Gdk.pixbuf_get_from_texture(texture)
    if pixbuf is None:
        msg = f"could not read look texture (GTK {_gtk_version()})"
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


def widget_rgb_retry(widget: object, x: int, y: int, tries: int = 24) -> tuple[int, int, int]:
    last_msg = ""
    for _ in range(tries):
        try:
            return widget_rgb(widget, x, y)
        except RuntimeError as exc:
            last_msg = str(exc)
            pump(4)
    raise RuntimeError(last_msg or "look widget produced no pixels")


def _without_gi_traceback(func: object, *args: object) -> object:
    """Re-raise as a string so pytest GC cannot collect GI objects in the traceback.

    Ubuntu 22.04's pygobject SIGSEGVs while pytest formats a failure whose frames
    still hold Gtk.Snapshot / GskRenderer wrappers.
    """

    def _run() -> tuple[str, object]:
        try:
            return ("ok", func(*args))  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            return ("err", f"{type(exc).__name__}: {exc}")

    status, payload = _run()
    if status == "err":
        raise RuntimeError(str(payload))
    return payload


def widget_panel_rgb(widget: object) -> tuple[int, int, int]:
    """Interior fill, sampled in the prompt band at the top of the panel.

    Horizontally centred, so no look's corner radius reaches it. Vertically near the top: the
    selected result row sits in the middle of the panel and is filled with the look's accent,
    so a centre sample reads the panel only while the results area happens to be short.
    """
    width = max(int(widget.get_width()), 1)
    height = max(int(widget.get_height()), 1)
    sample_x = max(width // 2, 8)
    sample_y = max(min(16, height - 4), 4)
    return widget_rgb_retry(widget, sample_x, sample_y)


def _destroy_tree(win: object) -> None:
    closer = getattr(win, "close", None)
    if callable(closer):
        closer()
    pump(8)


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


def _placeholder_rgb(entry: object, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    last_msg = ""
    targets = [_placeholder_label(entry), entry]
    seen: set[int] = set()
    for target in targets:
        ident = id(target)
        if ident in seen:
            continue
        seen.add(ident)
        try:
            pixbuf = widget_pixbuf(target)
            return _nearest_colored_rgb(pixbuf, expected)
        except RuntimeError as exc:
            last_msg = str(exc)
    raise RuntimeError(last_msg or "placeholder produced no colored pixels")


def _placeholder_rgb_retry(entry: object, expected: tuple[int, int, int], tries: int = 24) -> tuple[int, int, int]:
    last_msg = ""
    for _ in range(tries):
        try:
            return _placeholder_rgb(entry, expected)
        except RuntimeError as exc:
            last_msg = str(exc)
            pump(4)
    raise RuntimeError(last_msg or "placeholder produced no colored pixels")


def sample_look(look_id: str) -> dict[str, tuple[int, int, int]]:
    return _without_gi_traceback(_sample_look_impl, look_id)  # type: ignore[return-value]


def _sample_look_impl(look_id: str) -> dict[str, tuple[int, int, int]]:
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
        if (
            mapped["ok"]
            and prompt.get_width() > 40
            and selected.get_width() > 40
            and selected.get_height() > 10
            and _native_renderer(prompt) is not None
        ):
            break
    if prompt.get_width() <= 40 or selected.get_width() <= 40:
        _destroy_tree(win)
        msg = (
            f"look {look_id} did not allocate "
            f"(prompt {prompt.get_width()}x{prompt.get_height()}, "
            f"selected {selected.get_width()}x{selected.get_height()})"
        )
        raise RuntimeError(msg)
    pump(12)
    panel = prompt if look_id == "spotlight" else app
    panel_rgb = widget_panel_rgb(panel)
    # Label text sits on the start edge; sample trailing padding for the row fill.
    selected_x = max(int(selected.get_width()) - 16, 4)
    selected_y = max(int(selected.get_height()) // 2, 4)
    selected_rgb = widget_rgb_retry(selected, selected_x, selected_y)
    _destroy_tree(win)
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
    return _without_gi_traceback(_sample_popup_look_impl, look_id)  # type: ignore[return-value]


def _sample_popup_look_impl(look_id: str) -> dict[str, tuple[int, int, int]]:
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
    panel_rgb = widget_panel_rgb(panel)
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
    raise RuntimeError(str(last_error) if last_error is not None else "entry selection produced no pixels")


def sample_entry_selection(look_id: str) -> tuple[int, int, int]:
    """Paint a selected query so GTK4 ``selection`` CSS can be sampled."""
    return _without_gi_traceback(_sample_entry_selection_impl, look_id)  # type: ignore[return-value]


def _sample_entry_selection_impl(look_id: str) -> tuple[int, int, int]:
    from gi.repository import GLib

    win, app, prompt, _selected = build_look_tree(look_id)
    entry = _entry_in_prompt(prompt)
    if entry is None:
        _destroy_tree(win)
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
        _destroy_tree(win)


def sample_placeholder(look_id: str, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    """Paint an empty search hint so look ``text.placeholder`` CSS can be sampled."""
    return _without_gi_traceback(_sample_placeholder_impl, look_id, expected)  # type: ignore[return-value]


def _sample_placeholder_impl(look_id: str, expected: tuple[int, int, int]) -> tuple[int, int, int]:
    from gi.repository import GLib

    from ulauncher.modes.launcher.looks import get_look

    win, _app, prompt, _selected = build_look_tree(look_id)
    entry = _entry_in_prompt(prompt)
    if entry is None:
        _destroy_tree(win)
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
        return _placeholder_rgb_retry(entry, expected)
    finally:
        _destroy_tree(win)
