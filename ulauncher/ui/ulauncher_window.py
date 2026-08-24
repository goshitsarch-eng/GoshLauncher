from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from gi.repository import Gdk, Gtk

from ulauncher import paths
from ulauncher.internals.results_update import ResultsUpdate
from ulauncher.modes.launcher.looks import chrome_from_settings, ensure_look_chrome
from ulauncher.ui import gtk4
from ulauncher.ui.helpers import layer_shell
from ulauncher.ui.helpers.monitor import get_monitor, get_monitor_geometries
from ulauncher.ui.helpers.theme import Theme
from ulauncher.ui.load_icon_surface import load_icon_paintable
from ulauncher.ui.results_view import ResultsView
from ulauncher.utils import scheduling
from ulauncher.utils.environment import DESKTOP_ID, IS_X11_COMPATIBLE
from ulauncher.utils.settings import Settings

if TYPE_CHECKING:
    from ulauncher.ui.app import UlauncherApp

logger = logging.getLogger(__name__)


class UlauncherWindow(Gtk.ApplicationWindow):
    _css_provider: Gtk.CssProvider | None = None
    is_dragging = False
    layer_shell_enabled = False
    settings: Settings

    def __init__(self, **kwargs: Any) -> None:  # noqa: PLR0915
        logger.info("Opening Ulauncher window")
        self.settings = Settings.load(force=True)
        ensure_look_chrome(self.settings)
        self._chrome = chrome_from_settings(self.settings)
        width_request = self.settings.base_width
        height_request = -1

        if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE and (layout_size := self.get_layout_size()):
            width_request = layout_size.width
            height_request = layout_size.height

        super().__init__(
            decorated=False,
            deletable=False,
            resizable=False,
            title="Ulauncher - Application Launcher",
            **kwargs,
        )
        self.set_default_size(width_request, height_request if height_request > 0 else 1)
        self.set_opacity(0)

        if not IS_X11_COMPATIBLE and DESKTOP_ID != "GNOME" and self.settings.layer_shell and layer_shell.is_supported():
            self.layer_shell_enabled = layer_shell.enable(self)
            if self.layer_shell_enabled:
                logger.info("Layer shell support is enabled")
            else:
                logger.warning(
                    "Layer shell is not supported. If you have issues with window positioning, "
                    "ensure that your compositor supports it and that you have installed gtk4-layer-shell"
                )

        self.frame = Gtk.Box(valign=Gtk.Align.START, orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(self.frame)

        shadow = self._get_shadow_size()
        shadow_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shadow_container.set_margin_top(shadow)
        shadow_container.set_margin_bottom(shadow)
        shadow_container.set_margin_start(shadow)
        shadow_container.set_margin_end(shadow)
        gtk4.pack_start(self.frame, shadow_container, True, True, 0)

        self.theme_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        gtk4.pack_start(shadow_container, self.theme_root, True, True, 0)

        self.prompt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(self.prompt, "prompt")
        self.prompt_input = Gtk.Entry(hexpand=True, height_request=30)
        self.prompt_input.set_margin_top(15)
        self.prompt_input.set_margin_bottom(15)
        self.prompt_input.set_margin_start(20)
        self.prompt_input.set_margin_end(20)

        self.prefs_btn = Gtk.Button(name="prefs_btn", width_request=24, height_request=24)
        self.prefs_btn.set_halign(Gtk.Align.CENTER)
        self.prefs_btn.set_valign(Gtk.Align.CENTER)
        self.prefs_btn.set_margin_end(15)
        self.prefs_btn.set_can_focus(False)

        if self._chrome.get("show_search_icon", True):
            search_icon = Gtk.Image(icon_name="system-search", pixel_size=16)
            gtk4.add_css_class(search_icon, "search-icon")
            search_icon.set_margin_start(12)
            gtk4.pack_start(self.prompt, search_icon, False, False, 0)
        gtk4.pack_start(self.prompt, self.prompt_input, True, True, 0)
        gtk4.pack_end(self.prompt, self.prefs_btn, False, False, 0)

        self.results_view = ResultsView(self.settings, self.apply_css, self.activate_result)

        gtk4.pack_start(self.theme_root, self.prompt, False, True, 0)
        gtk4.pack_start(self.theme_root, self.results_view, False, True, 0)
        gtk4.show_all(self.frame)

        focus = Gtk.EventControllerFocus()
        focus.connect("enter", lambda *_: self.on_focus_in())
        focus.connect("leave", lambda *_: self.on_focus_out())
        self.add_controller(focus)

        drag = Gtk.GestureClick()
        drag.connect("pressed", self.on_mouse_down)
        drag.connect("released", lambda *_: self.on_mouse_up())
        self.prompt.add_controller(drag)

        self.prompt_input.connect("changed", lambda *_: self.on_input_changed())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_input_key_press)
        self.prompt_input.add_controller(keys)
        self.connect("map", self.on_initial_draw)
        self.prefs_btn.connect("clicked", lambda *_: self.get_app().show_preferences())

        self.present()
        super().set_visible(True)

        if self.query_str:
            self.set_input(self.query_str)

    def apply_styling(self) -> None:
        if self.get_opacity() == 1:
            return

        gtk4.add_css_class(self.theme_root, "app")
        gtk4.add_css_class(self.theme_root, f"gosh-theme-{getattr(self.settings, 'look_id', 'spotlight')}")
        gtk4.add_css_class(self.theme_root, f"gosh-density-{self._chrome.get('density') or 'comfortable'}")
        if not self._chrome.get("show_search_icon", True):
            gtk4.add_css_class(self.theme_root, "gosh-no-search-icon")
        gtk4.add_css_class(self.prompt, "prompt")
        gtk4.add_css_class(self.results_view, "result-box")
        gtk4.add_css_class(self.prompt_input, "input")
        gtk4.add_css_class(self.prefs_btn, "prefs-btn")
        paintable = load_icon_paintable(f"{paths.ASSETS}/icons/gear.svg", 16, self.get_scale_factor())
        self.prefs_btn.set_child(Gtk.Image.new_from_paintable(paintable))

        self.apply_theme()
        self.position_window()
        self.set_opacity(1)

    def deferred_init(self) -> None:
        if not self.get_application():
            return
        if self.query_str:
            self.prompt_input.select_region(0, -1)
        self.apply_styling()
        self.get_app().window_ready()

    def on_initial_draw(self, *_: Any) -> None:
        if t0 := os.environ.get("ULAUNCHER_PERF_START_BOOTTIME"):
            elapsed_ms = (time.clock_gettime(time.CLOCK_BOOTTIME) - float(t0)) * 1000
            sys.stdout.write(f"ULAUNCHER_PERF first_draw_ms={elapsed_ms:.2f}\n")
            sys.stdout.flush()
            if app := self.get_application():
                app.quit()
            return
        logger.info("Window shown")
        with contextlib.suppress(TypeError):
            self.disconnect_by_func(self.on_initial_draw)
        scheduling.run_when_idle(self.deferred_init)

    def on_focus_out(self) -> None:
        if self.settings.close_on_focus_out and not self.is_dragging:
            self.close(save_query=True)

    def on_focus_in(self) -> None:
        if self.settings.grab_mouse_pointer:
            self.toggle_grab_pointer_device(True)

    def on_input_changed(self) -> None:
        self.get_app().query_changed(self.prompt_input.get_text())

    def activate_result(self, alt: bool) -> None:
        if result := self.results_view.get_active_result():
            self.get_app().activate_result(result, alt)

    def on_input_key_press(  # noqa: PLR0911, PLR0912
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        keyname = Gdk.keyval_name(keyval) or ""
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        jump_keys = self.settings.get_jump_keys()

        use_arrow_key_aliases = len(self.settings.arrow_key_aliases) == 4  # noqa: PLR2004
        arrow_key_aliases = [*self.settings.arrow_key_aliases] if use_arrow_key_aliases else [None] * 4
        left_alias, down_alias, up_alias, right_alias = arrow_key_aliases
        if not use_arrow_key_aliases:
            logger.warning(
                "Invalid value for arrow_key_aliases: %s, expected four letters", self.settings.arrow_key_aliases
            )

        if keyname == "Escape":
            self.close(save_query=True)
            return True

        if ctrl and keyname == "comma":
            self.get_app().show_preferences()
            return True

        entry = self.prompt_input
        if (
            keyname == "BackSpace"
            and not ctrl
            and not entry.get_selection_bounds()
            and entry.get_position() == len(self.query_str)
            and self.get_app().handle_backspace(self.query_str)
        ):
            return True

        if self.results_view.has_results:
            if keyname in ("Up", "ISO_Left_Tab") or (ctrl and keyname in (up_alias, "k", "p")):
                self.results_view.go_up()
                return True
            if keyname in ("Down", "Tab") or (ctrl and keyname in (down_alias, "j", "n")):
                self.results_view.go_down()
                return True
            if keyname == "Page_Up":
                self.results_view.go_page_up()
                return True
            if keyname == "Page_Down":
                self.results_view.go_page_down()
                return True
            cursor = entry.get_position()
            text_len = len(entry.get_text() or "")
            if keyname == "Home" and cursor == 0:
                self.results_view.go_home()
                return True
            if keyname == "End" and cursor == text_len:
                self.results_view.go_end()
                return True
            if ctrl and keyname == left_alias:
                entry.set_position(max(0, cursor - 1))
                return True
            if ctrl and keyname == right_alias:
                entry.set_position(cursor + 1)
                return True
            if keyname in ("Return", "KP_Enter"):
                self.activate_result(alt)
                return True
            string = chr(Gdk.keyval_to_unicode(keyval)) if Gdk.keyval_to_unicode(keyval) else ""
            if alt and string in jump_keys:
                if string.isdigit() and not self._chrome.get("show_numbers"):
                    return False
                self.results_view.select_jump(jump_keys.index(string))
                return True
        return False

    def on_mouse_down(self, gesture: Gtk.GestureClick, _n_press: int, x: float, y: float) -> None:
        if gesture.get_current_button() != 1:
            return
        self.is_dragging = True
        native = self.get_native()
        surface = native.get_surface() if native else None
        device = gesture.get_device()
        event = gesture.get_last_event(None)
        timestamp = event.get_time() if event else Gdk.CURRENT_TIME
        if surface is not None and device is not None and hasattr(surface, "begin_move"):
            surface.begin_move(device, 1, int(x), int(y), timestamp)

    def on_mouse_up(self, *_args: Any) -> None:
        self.is_dragging = False

    def get_app(self) -> UlauncherApp:
        return cast("UlauncherApp", self.get_application())

    @property
    def query_str(self) -> str:
        return self.get_app().query

    def apply_css(self, widget: Gtk.Widget) -> None:
        if not self._css_provider:
            self._css_provider = Gtk.CssProvider()
        widget.get_style_context().add_provider(self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for child in gtk4.iter_children(widget):
            self.apply_css(child)

    def _get_shadow_size(self) -> int:
        display = self.get_display()
        if display and hasattr(display, "is_composited") and not display.is_composited():
            return 0
        return self.settings.window_shadow

    def apply_theme(self) -> None:
        if not self._css_provider:
            self._css_provider = Gtk.CssProvider()
        theme_css = Theme.load(self.settings.theme_name).get_css(self._get_shadow_size())
        looks_path = Path(paths.ASSETS) / "themes" / "gosh-looks.css"
        if looks_path.is_file():
            theme_css += "\n" + looks_path.read_text()
        self._css_provider.load_from_data(theme_css.encode())
        self.apply_css(self)
        logger.info('Applying theme "%s"', self.settings.theme_name)

    def get_layout_size(self) -> Gdk.Rectangle | None:
        if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE:
            if not (geometries := get_monitor_geometries()):
                return None
            layout_size = Gdk.Rectangle()
            layout_size.width = min(geometry.width for geometry in geometries)
            layout_size.height = min(geometry.height for geometry in geometries)
            return layout_size
        if monitor := get_monitor(self.settings.render_on_screen != "default-monitor"):
            return monitor.get_geometry()
        return None

    def position_window(self) -> None:
        if layout_size := self.get_layout_size():
            window_width = self.settings.base_width
            pos_x = (layout_size.width - window_width) / 2
            pos_y = layout_size.height * (0.02 if self._chrome.get("position") == "top" else 0.1)
            prompt_height = self.prompt.get_allocated_height() or 60
            max_height = int(getattr(self.settings, "results_max_height", 400) or 400)
            self.results_view.set_max_height(int(min(max_height, layout_size.height - prompt_height - pos_y * 2)))

            if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE:
                self.frame.set_margin_top(int(pos_y))
                self.frame.set_margin_bottom(int(pos_y))
                self.frame.set_margin_start(int(pos_x))
                self.frame.set_margin_end(int(pos_x))
            elif self.layer_shell_enabled:
                layer_shell.set_vertical_position(self, pos_y)
            elif hasattr(self, "move"):
                self.move(int(pos_x + getattr(layout_size, "x", 0)), int(pos_y + getattr(layout_size, "y", 0)))

    def close(self, save_query: bool = False) -> None:  # type: ignore[override]
        logger.info("Closing Ulauncher window")
        if not save_query or not self.settings.auto_resume:
            self.get_app().set_query("", update_input=False)
        if self.settings.grab_mouse_pointer:
            self.toggle_grab_pointer_device(False)
        super().close()
        self.destroy()

    def toggle_grab_pointer_device(self, grab: bool) -> None:
        display = self.get_display()
        seat = display.get_default_seat() if display else None
        if not seat:
            logger.warning("Could not get the pointer device.")
            return
        if not grab:
            ungrab = getattr(seat, "ungrab", None)
            if callable(ungrab):
                ungrab()
            return
        grab_fn = getattr(seat, "grab", None)
        native = self.get_native()
        surface = native.get_surface() if native else None
        if not callable(grab_fn) or surface is None:
            logger.debug("Pointer grab is not available on this GTK4 display")
            return
        grab_status = grab_fn(surface, Gdk.SeatCapabilities.ALL_POINTING, True)
        logger.debug("Focus in event, grabbing pointer: %s", grab_status)

    def set_input(self, query_str: str) -> None:
        self.prompt_input.set_text(query_str)
        self.prompt_input.set_position(-1)

    def show_results(self, update: ResultsUpdate) -> None:
        self.results_view.render(update)
