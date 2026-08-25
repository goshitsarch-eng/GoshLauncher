from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Collection, cast

from gi.repository import Gdk, Gtk

from ulauncher import app_display_name, paths
from ulauncher.internals.results_update import ResultsUpdate
from ulauncher.modes.launcher.looks import chrome_from_settings, ensure_look_chrome
from ulauncher.ui import gtk4
from ulauncher.ui.helpers import layer_shell
from ulauncher.ui.helpers.monitor import get_monitor, get_monitor_geometries, monitor_work_geometry
from ulauncher.ui.helpers.theme import launcher_popup_css
from ulauncher.ui.results_view import ResultsView
from ulauncher.utils import scheduling
from ulauncher.utils.environment import DESKTOP_ID, IS_X11_COMPATIBLE
from ulauncher.utils.settings import Settings

if TYPE_CHECKING:
    from ulauncher.ui.app import UlauncherApp

logger = logging.getLogger(__name__)


def _read_entry_preedit(entry: Any) -> str:
    from ulauncher.modes.launcher.key_action import read_preedit

    getter = getattr(entry, "get_preedit_string", None)
    if callable(getter):
        return read_preedit(getter())
    delegate_fn = getattr(entry, "get_delegate", None)
    delegate = delegate_fn() if callable(delegate_fn) else None
    if delegate is not None and delegate is not entry:
        return _read_entry_preedit(delegate)
    return ""


def _event_time_us(controller: Any) -> int:
    getter = getattr(controller, "get_current_event_time", None)
    if not callable(getter):
        return 0
    time_ms = int(getter() or 0)
    if time_ms <= 0:
        return 0
    return time_ms * 1000


class UlauncherWindow(Gtk.ApplicationWindow):
    _css_provider: Gtk.CssProvider | None = None
    _css_on_display = False
    _styled = False
    is_dragging = False
    layer_shell_enabled = False
    settings: Settings

    def __init__(self, **kwargs: Any) -> None:  # noqa: PLR0915
        logger.info("Opening %s window", app_display_name)
        self.settings = Settings.load(force=True)
        ensure_look_chrome(self.settings)
        self._chrome = chrome_from_settings(self.settings)
        self._nav_last_key = 0
        self._nav_last_time_us = 0
        self._backdrop = None
        self._backdrop_close_idle = None
        self._prefs_layout_idle = None
        self._input_chrome_idle = None
        self._refocus_idle = None
        self._unredirect_held = False
        self._unredirect_restore: Any = None
        self._osk_visible = False
        self._scale_watched = False
        width_request = self.settings.base_width
        height_request = -1

        if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE and (layout_size := self.get_layout_size()):
            width_request = layout_size.width
            height_request = layout_size.height

        from ulauncher.modes.launcher.popup_position import gtk_default_window_size

        super().__init__(
            decorated=False,
            deletable=False,
            resizable=False,
            title=app_display_name,
            **kwargs,
        )
        gtk4.add_css_class(self, "gosh-popup")
        default_w, default_h = gtk_default_window_size(width_request, height_request)
        self.set_default_size(default_w, default_h)

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

        self.shadow_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        gtk4.pack_start(self.frame, self.shadow_container, True, True, 0)
        self._sync_shadow_inset()

        self.theme_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.theme_root.set_can_focus(False)
        gtk4.pack_start(self.shadow_container, self.theme_root, True, True, 0)

        self.prompt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.prompt.set_can_focus(False)
        gtk4.add_css_class(self.prompt, "prompt")
        self.prompt_input = Gtk.Entry(hexpand=True)
        # CSS .input padding is the inset; widget margins would ignore look/no-icon rules

        from ulauncher.modes.launcher.focus_loss import popup_chrome_should_focus
        from ulauncher.modes.launcher.search_entry import SEARCH_ICON_NAME, SEARCH_ICON_PX

        self.search_icon = Gtk.Image(icon_name=SEARCH_ICON_NAME, pixel_size=SEARCH_ICON_PX)
        self.search_icon.set_can_focus(popup_chrome_should_focus())
        gtk4.add_css_class(self.search_icon, "search-icon")
        self.search_icon.set_valign(Gtk.Align.CENTER)
        gtk4.pack_start(self.prompt, self.search_icon, False, False, 0)
        gtk4.pack_start(self.prompt, self.prompt_input, True, True, 0)
        self._sync_search_entry()

        self.results_view = ResultsView(self.settings, self.apply_css, self._activate_clicked)
        self.results_view.set_chrome(self._chrome)

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

        backdrop = Gtk.GestureClick()
        backdrop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        backdrop.connect("pressed", self.on_backdrop_pressed)
        backdrop.connect("released", self.on_backdrop_released)
        self.add_controller(backdrop)

        self.prompt_input.connect("changed", lambda *_: self.on_input_changed())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_input_key_press)
        self.prompt_input.add_controller(keys)
        self.connect("map", self.on_initial_draw)

        # Style before the first map so GSK builds a tree (opacity 0 skipped paints).
        self.apply_styling()
        self._apply_unredirect(True)
        self._show_backdrop()
        self._sync_gnome_wayland_overlay()
        self.present()
        super().set_visible(True)

        if self.query_str:
            self.set_input(self.query_str)

    def apply_styling(self) -> None:
        if self._styled:
            return
        self._styled = True

        self._apply_look_classes()
        self._sync_search_entry()
        gtk4.add_css_class(self.prompt, "prompt")
        gtk4.add_css_class(self.results_view, "result-box")
        gtk4.add_css_class(self.prompt_input, "input")

        self.apply_theme()
        self.position_window()
        self.set_opacity(1)

    def _apply_look_classes(self) -> None:
        for css_class in list(self.theme_root.get_css_classes()):
            if (
                css_class.startswith(("gosh-theme-", "gosh-density-", "gosh-accent-"))
                or css_class == "gosh-no-search-icon"
            ):
                gtk4.remove_css_class(self.theme_root, css_class)
        gtk4.add_css_class(self.theme_root, "app")
        look_id = getattr(self.settings, "look_id", "spotlight")
        gtk4.add_css_class(self.theme_root, f"gosh-theme-{look_id}")
        gtk4.add_css_class(self.theme_root, f"gosh-density-{self._chrome.get('density') or 'comfortable'}")
        self._sync_shadow_inset()
        from ulauncher.modes.launcher.looks import search_icon_style_class

        icon_class = search_icon_style_class(bool(self._chrome.get("show_search_icon", True)))
        if icon_class:
            gtk4.add_css_class(self.theme_root, icon_class)
        from ulauncher.modes.launcher.accent import accent_style_class, session_accent_nick

        accent = accent_style_class(look_id, session_accent_nick())
        if accent:
            gtk4.add_css_class(self.theme_root, accent)
        self._ensure_accent_watch()

    def _sync_search_entry(self) -> None:
        from ulauncher.modes.launcher.search_entry import search_entry_spec

        spec = search_entry_spec(
            {
                "look_id": getattr(self.settings, "look_id", "spotlight"),
                "show_search_icon": bool(self._chrome.get("show_search_icon", True)),
            }
        )
        self.prompt_input.set_placeholder_text(spec["placeholder"])
        self.search_icon.set_pixel_size(spec["icon_px"])
        self.search_icon.set_visible(spec["icon_visible"])

    def _ensure_accent_watch(self) -> None:
        if getattr(self, "_accent_watched", False):
            return
        self._accent_watched = True
        from ulauncher.gi import Gio, GLib
        from ulauncher.modes.launcher.accent import next_accent_listen_action

        try:
            source = Gio.SettingsSchemaSource.get_default()
            schema = source.lookup("org.gnome.desktop.interface", True) if source else None
            if next_accent_listen_action(schema) != "listen":
                return
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            settings.connect("changed::accent-color", lambda *_: self._apply_look_classes())
            self._accent_settings = settings
        except (GLib.GError, AttributeError, TypeError, RuntimeError, OSError):
            return

    def restyle_from_settings(self) -> None:
        self.settings = Settings.load(force=True)
        ensure_look_chrome(self.settings)
        self._chrome = chrome_from_settings(self.settings)
        self.results_view.set_chrome(self._chrome)
        self._apply_look_classes()
        self._sync_search_entry()
        self.apply_theme()
        self.position_window()

    def apply_live_prefs(self, actions: Collection[str]) -> None:
        """Apply a prefs write the way goshos does while the popup is open."""
        from ulauncher.modes.launcher.prefs_live import (
            ACTION_FIT_HEIGHT,
            ACTION_LAYOUT,
            ACTION_POSITION,
            ACTION_REPAINT,
            ACTION_RESTYLE,
            ACTION_SEARCH_ICON,
        )

        action_set = set(actions)
        if not action_set:
            return
        if ACTION_RESTYLE in action_set:
            self.restyle_from_settings()
        else:
            self._chrome = chrome_from_settings(self.settings)
            self.results_view.set_chrome(self._chrome)
            if ACTION_SEARCH_ICON in action_set:
                self._apply_look_classes()
                self._sync_search_entry()
        if {ACTION_LAYOUT, ACTION_POSITION, ACTION_FIT_HEIGHT} & action_set:
            self._schedule_live_layout()
        if ACTION_REPAINT in action_set:
            self._on_live_search_change()

    def _schedule_live_layout(self) -> None:
        from ulauncher.modes.launcher.prefs_live import (
            should_apply_layout_immediately,
            should_schedule_live_idle,
        )

        is_open = bool(self.get_mapped())
        if should_apply_layout_immediately(is_open):
            self.position_window()
            return
        if not should_schedule_live_idle(bool(self._prefs_layout_idle), True):
            return
        self._prefs_layout_idle = scheduling.run_when_idle(self._run_live_layout)

    def _run_live_layout(self) -> None:
        from ulauncher.modes.launcher.prefs_live import should_run_live_idle

        self._prefs_layout_idle = None
        if should_run_live_idle(bool(self.get_mapped())):
            self.position_window()

    def _cancel_live_layout(self) -> None:
        idle = getattr(self, "_prefs_layout_idle", None)
        if idle:
            idle.cancel()
            self._prefs_layout_idle = None

    def deferred_init(self) -> None:
        if not self.get_application():
            return
        if self.query_str:
            self.prompt_input.select_region(0, -1)
        self.apply_styling()
        self.get_app().window_ready()
        self._ensure_monitor_watch()
        self._ensure_scale_watch()
        self._start_live_search()
        self._start_session_watch()
        self._start_osk_watch()
        self._raise_input_chrome()
        self._start_limits_timer()

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
        from ulauncher.modes.launcher.focus_loss import gtk_window_focus_action, should_run_refocus
        from ulauncher.modes.launcher.ime import ime_panel_visible

        if self.is_dragging:
            return
        ime_panel = ime_panel_visible()
        self._sync_input_chrome_layer(ime_panel=ime_panel)
        action = gtk_window_focus_action(
            bool(self.is_active()),
            self.get_focus(),
            self.prompt_input,
            ime_panel=ime_panel,
            osk_contains_focus=self._osk_visible,
        )
        if action == "close" and self.settings.close_on_focus_out:
            self.get_app().request_close(save_query=True)
            return
        if action == "refocus-entry" and should_run_refocus(self.get_mapped(), self.get_visible()):
            self._refocus_entry_soon()

    def on_focus_in(self) -> None:
        if self.settings.grab_mouse_pointer:
            self.toggle_grab_pointer_device(True)

    def on_input_changed(self) -> None:
        self.get_app().query_changed(self.prompt_input.get_text())

    def activate_result(self, alt: bool, fallback: bool = True) -> None:
        from ulauncher.modes.launcher.activate import activatable_result, indexed_activatable_result

        results = self.results_view.get_result_objects()
        index = self.results_view.selected_index
        chosen = activatable_result(results, index) if fallback else indexed_activatable_result(results, index)
        if chosen:
            self.get_app().activate_result(chosen, alt)
            return
        self._refocus_entry_soon()

    def _activate_clicked(self, alt: bool) -> None:
        self.activate_result(alt, fallback=False)

    def _activate_numbered(self, index: int) -> None:
        from ulauncher.modes.launcher.activate import indexed_activatable_result

        chosen = indexed_activatable_result(self.results_view.numbered_results(), index)
        if chosen:
            self.get_app().activate_result(chosen, False)

    def _apply_move(self, delta: int) -> None:
        if delta <= -999:  # noqa: PLR2004
            self.results_view.go_home()
        elif delta >= 999:  # noqa: PLR2004
            self.results_view.go_end()
        elif delta >= 5:  # noqa: PLR2004
            self.results_view.go_page_down()
        elif delta <= -5:  # noqa: PLR2004
            self.results_view.go_page_up()
        elif delta > 0:
            self.results_view.go_down()
        elif delta < 0:
            self.results_view.go_up()

    def on_input_key_press(  # noqa: PLR0911, PLR0912, PLR0915
        self, controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        from ulauncher.modes.launcher.ime import ime_panel_visible
        from ulauncher.modes.launcher.key_action import (
            resolve_ctrl_nav,
            resolve_home_end_action,
            resolve_key_action,
            should_defer_activate_for_preedit,
            should_propagate_for_ime,
        )
        from ulauncher.modes.launcher.nav_repeat import should_ignore_nav_repeat

        keyname = Gdk.keyval_name(keyval) or ""
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        show_numbers = bool(self._chrome.get("show_numbers"))

        entry = self.prompt_input
        preedit = _read_entry_preedit(entry)
        now_us = _event_time_us(controller)
        candidate_visible = False if preedit else ime_panel_visible()
        # Compose and IBus lookup consume every key first, including Escape.
        if should_propagate_for_ime(preedit, candidate_visible):
            self._raise_input_chrome(ime_panel=candidate_visible)
            return False

        if keyname == "Escape":
            self.get_app().request_close(save_query=True)
            return True

        if ctrl and keyname == "comma":
            self.get_app().show_preferences()
            return True

        if (
            keyname == "BackSpace"
            and not ctrl
            and not entry.get_selection_bounds()
            and entry.get_position() == len(self.query_str)
            and self.get_app().handle_backspace(self.query_str)
        ):
            return True

        if ctrl:
            nav = resolve_ctrl_nav(keyname)
            if nav and self.results_view.has_results:
                if should_ignore_nav_repeat(keyval, self._nav_last_key, now_us, self._nav_last_time_us):
                    return True
                self._nav_last_key = keyval
                self._nav_last_time_us = now_us
                self._apply_move(int(nav["delta"]))
                return True

        cursor = entry.get_position()
        text_len = len(entry.get_text() or "")
        home_end = resolve_home_end_action(keyname, cursor, text_len)
        if home_end:
            if home_end["type"] == "propagate":
                return False
            if self.results_view.has_results:
                if should_ignore_nav_repeat(keyval, self._nav_last_key, now_us, self._nav_last_time_us):
                    return True
                self._nav_last_key = keyval
                self._nav_last_time_us = now_us
                self._apply_move(int(home_end["delta"]))
                return True
            return False

        action = resolve_key_action(keyname, shift, alt, show_numbers)
        if action["type"] == "close":
            self.get_app().request_close(save_query=True)
            return True
        if action["type"] == "close-and-propagate":
            self.get_app().request_close(save_query=True)
            return False
        if action["type"] == "move" and self.results_view.has_results:
            if should_ignore_nav_repeat(keyval, self._nav_last_key, now_us, self._nav_last_time_us):
                return True
            self._nav_last_key = keyval
            self._nav_last_time_us = now_us
            self._apply_move(int(action["delta"]))
            return True
        if action["type"] in {"activate", "activate-index"} and should_defer_activate_for_preedit(preedit):
            return False
        if action["type"] == "activate" and self.results_view.has_results:
            self.activate_result(alt)
            return True
        if action["type"] == "activate-index":
            self._activate_numbered(int(action["index"]))
            return True
        return False

    def on_mouse_down(self, gesture: Gtk.GestureClick, _n_press: int, x: float, y: float) -> None:
        if gesture.get_current_button() != 1:
            return
        from ulauncher.modes.launcher.focus_loss import prompt_click_should_drag, prompt_click_should_refocus

        target = self._prompt_click_target(x, y)
        if prompt_click_should_refocus(target):
            self._refocus_entry_soon()
        if not prompt_click_should_drag(target):
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
        was_dragging = self.is_dragging
        self.is_dragging = False
        if was_dragging:
            self._refocus_entry_soon()

    def _widget_rect_in_prompt(self, widget: Gtk.Widget) -> tuple[float, float, float, float]:
        compute = getattr(widget, "compute_bounds", None)
        if callable(compute):
            ok, bounds = compute(self.prompt)
            if ok and bounds is not None:
                get_x = getattr(bounds, "get_x", None)
                if callable(get_x):
                    return (
                        float(bounds.get_x()),
                        float(bounds.get_y()),
                        float(bounds.get_width()),
                        float(bounds.get_height()),
                    )
                return (float(bounds.x), float(bounds.y), float(bounds.width), float(bounds.height))
        return (0.0, 0.0, 0.0, 0.0)

    def _prompt_click_target(self, x: float, y: float) -> str:
        from ulauncher.modes.launcher.focus_loss import prompt_click_target

        return prompt_click_target(
            x,
            y,
            self._widget_rect_in_prompt(self.search_icon),
            self._widget_rect_in_prompt(self.prompt_input),
        )

    def _refocus_entry_soon(self) -> None:
        pending = getattr(self, "_refocus_idle", None)
        if pending is not None:
            return
        self._refocus_idle = scheduling.run_when_idle(self._run_refocus_entry)

    def _run_refocus_entry(self) -> None:
        from ulauncher.modes.launcher.focus_loss import should_run_refocus

        self._refocus_idle = None
        if should_run_refocus(self.get_mapped(), self.get_visible()):
            self.prompt_input.grab_focus()

    def _cancel_refocus_idle(self) -> None:
        idle = getattr(self, "_refocus_idle", None)
        if idle:
            idle.cancel()
        self._refocus_idle = None

    def _click_outside_card(self, x: float, y: float) -> bool:
        from ulauncher.modes.launcher.click_outside import click_is_outside_card

        compute = getattr(self.theme_root, "compute_bounds", None)
        if callable(compute):
            ok, bounds = compute(self)
            if ok:
                return click_is_outside_card(
                    x - bounds.get_x(),
                    y - bounds.get_y(),
                    bounds.get_width(),
                    bounds.get_height(),
                )
        width = float(self.theme_root.get_width() or 0)
        height = float(self.theme_root.get_height() or 0)
        return click_is_outside_card(x, y, width, height)

    def on_backdrop_pressed(self, gesture: Gtk.GestureClick, _n_press: int, x: float, y: float) -> None:
        from ulauncher.modes.launcher.click_outside import backdrop_claims_event

        if not self._click_outside_card(x, y):
            return
        if backdrop_claims_event("button-press"):
            state = getattr(Gtk, "EventSequenceState", None)
            if state is not None:
                gesture.set_state(state.CLAIMED)

    def on_backdrop_released(self, _gesture: Gtk.GestureClick, _n_press: int, x: float, y: float) -> None:
        from ulauncher.modes.launcher.click_outside import backdrop_should_close

        if self._click_outside_card(x, y) and backdrop_should_close("button-release"):
            self.get_app().request_close(save_query=True)

    def get_app(self) -> UlauncherApp:
        return cast("UlauncherApp", self.get_application())

    @property
    def query_str(self) -> str:
        return self.get_app().query

    def apply_css(self, widget: Gtk.Widget) -> None:
        if getattr(self, "_css_on_display", False) or not self._css_provider:
            return
        display = widget.get_display() or Gdk.Display.get_default()
        if not display:
            return
        gtk4.add_provider_to_display(self._css_provider)
        self._css_on_display = True

    def apply_theme(self) -> None:
        css = launcher_popup_css()
        if not self._css_provider:
            self._css_provider = gtk4.load_css_provider(css)
            display = self.get_display() or Gdk.Display.get_default()
            if display:
                gtk4.add_provider_to_display(self._css_provider)
                self._css_on_display = True
            else:
                self.apply_css(self)
        else:
            self._css_provider.load_from_data(css.encode())
            if not getattr(self, "_css_on_display", False):
                self.apply_css(self)
        logger.info('Applying look "%s"', getattr(self.settings, "look_id", "spotlight"))

    def _sync_shadow_inset(self) -> int:
        from ulauncher.modes.launcher.popup_shadow import look_shadow_inset

        display = self.get_display()
        if display and hasattr(display, "is_composited") and not display.is_composited():
            inset = 0
        else:
            looks_path = Path(paths.ASSETS) / "themes" / "gosh-looks.css"
            css = looks_path.read_text() if looks_path.is_file() else ""
            inset = look_shadow_inset(css, str(getattr(self.settings, "look_id", "spotlight") or "spotlight"))
        box = getattr(self, "shadow_container", None)
        if box is not None:
            box.set_margin_top(inset)
            box.set_margin_bottom(inset)
            box.set_margin_start(inset)
            box.set_margin_end(inset)
        return inset

    def get_layout_size(self) -> Gdk.Rectangle | None:
        from ulauncher.modes.launcher.popup_position import gnome_wayland_overlay_size

        mouse = self.settings.render_on_screen != "default-monitor"
        if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE:
            monitor = get_monitor(mouse)
            selected = None
            if monitor is not None:
                geo = monitor.get_geometry()
                selected = {"x": geo.x, "y": geo.y, "width": geo.width, "height": geo.height}
            geometries = [{"x": g.x, "y": g.y, "width": g.width, "height": g.height} for g in get_monitor_geometries()]
            overlay = gnome_wayland_overlay_size(selected, geometries)
            if not overlay:
                return None
            layout_size = Gdk.Rectangle()
            layout_size.x = overlay["x"]
            layout_size.y = overlay["y"]
            layout_size.width = overlay["width"]
            layout_size.height = overlay["height"]
            return layout_size
        if monitor := get_monitor(mouse):
            return monitor_work_geometry(monitor)
        return None

    def _sync_gnome_wayland_overlay(self) -> None:
        if DESKTOP_ID != "GNOME" or IS_X11_COMPATIBLE:
            return
        monitor = get_monitor(self.settings.render_on_screen != "default-monitor")
        fullscreen_on = getattr(self, "fullscreen_on_monitor", None)
        if callable(fullscreen_on) and monitor is not None:
            fullscreen_on(monitor)

    def position_window(self) -> None:
        from ulauncher.modes.launcher.chrome_size import clamp_popup_width, clamp_results_max_height
        from ulauncher.modes.launcher.osk import osk_keyboard_for_work_area
        from ulauncher.modes.launcher.popup_position import (
            empty_popup_height,
            gtk_window_owns_popup_width,
            offset_from_origin,
            place_popup,
            popup_surface_can_move,
            popup_surface_move,
            popup_width_for_work_area,
            work_area_avoiding_keyboard,
        )
        from ulauncher.modes.launcher.popup_shadow import origin_minus_inset, surface_size_with_inset
        from ulauncher.modes.launcher.ui_scale import gtk_layout_scale

        self._sync_gnome_wayland_overlay()
        if layout_size := self.get_layout_size():
            work = {
                "x": int(getattr(layout_size, "x", 0) or 0),
                "y": int(getattr(layout_size, "y", 0) or 0),
                "width": int(layout_size.width),
                "height": int(layout_size.height),
            }
            # GTK geometry is already CSS px; St scale_factor would double the card
            scale = gtk_layout_scale(self.get_scale_factor())
            work = work_area_avoiding_keyboard(
                work,
                osk_keyboard_for_work_area(work, bool(getattr(self, "_osk_visible", False))),
            )
            requested_width = clamp_popup_width(int(self.settings.base_width))
            popup_width = popup_width_for_work_area(requested_width, work["width"], scale)
            measured = self.prompt.measure(Gtk.Orientation.VERTICAL, popup_width)
            empty_height = empty_popup_height(int(measured[1]))
            position = str(self._chrome.get("position") or "center")
            requested = clamp_results_max_height(int(getattr(self.settings, "results_max_height", 400) or 400))
            placed = place_popup(work, popup_width, empty_height, position, requested, None, scale)
            surface = work
            if self.layer_shell_enabled and (
                monitor := get_monitor(self.settings.render_on_screen != "default-monitor")
            ):
                geo = monitor.get_geometry()
                surface = {"x": int(geo.x), "y": int(geo.y)}
            offset = offset_from_origin(placed, surface)
            inset = self._sync_shadow_inset()
            pos_x = origin_minus_inset(offset["x"], inset)
            pos_y = origin_minus_inset(offset["y"], inset)
            frame_width = surface_size_with_inset(popup_width, inset)
            self.results_view.set_max_height(int(placed["results_max"]))
            if gtk_window_owns_popup_width(DESKTOP_ID, IS_X11_COMPATIBLE):
                self.set_default_size(frame_width, -1)

            if DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE:
                self.frame.set_margin_top(pos_y)
                self.frame.set_margin_bottom(0)
                self.frame.set_margin_start(pos_x)
                self.frame.set_margin_end(max(0, int(work["width"] - pos_x - frame_width)))
            elif self.layer_shell_enabled:
                layer_shell.set_position(self, pos_x, pos_y)
            else:
                native = self.get_native()
                gdk_surface = native.get_surface() if native is not None else None
                if popup_surface_can_move(gdk_surface):
                    popup_surface_move(
                        gdk_surface,
                        origin_minus_inset(placed["x"], inset),
                        origin_minus_inset(placed["y"], inset),
                    )

    def _ensure_monitor_watch(self) -> None:
        if getattr(self, "_monitors_watched", False):
            return
        display = self.get_display()
        if display is None:
            return
        monitors = display.get_monitors()
        monitors.connect("items-changed", lambda *_args: self._on_monitors_changed())
        self._monitors_model = monitors
        self._monitors_watched = True

    def _on_monitors_changed(self) -> None:
        self.position_window()
        self._relayout_backdrop()

    def _start_live_search(self) -> None:
        from ulauncher.modes.launcher.live_search import LiveSearchWatcher
        from ulauncher.modes.launcher.search_live import next_live_search_action

        if getattr(self, "_live_search", None) is None:
            self._live_search = LiveSearchWatcher(self._on_live_search_change)
            self._live_idle = None
        if next_live_search_action(self._live_search.listening, True) == "start":
            self._live_search.start()

    def _ensure_scale_watch(self) -> None:
        from ulauncher.gi import Gio, GLib
        from ulauncher.modes.launcher.ui_scale import next_scale_listen_action

        if next_scale_listen_action(bool(getattr(self, "_scale_watched", False)), self) != "listen":
            return
        self._scale_watched = True
        self.connect("notify::scale-factor", lambda *_: self._on_scale_changed())
        try:
            source = Gio.SettingsSchemaSource.get_default()
            schema = source.lookup("org.gnome.desktop.interface", True) if source else None
            if schema is None:
                return
            settings = getattr(self, "_accent_settings", None) or Gio.Settings.new("org.gnome.desktop.interface")
            settings.connect("changed::text-scaling-factor", lambda *_: self._on_scale_changed())
            self._interface_settings = settings
        except (GLib.GError, AttributeError, TypeError, RuntimeError, OSError):
            return

    def _on_scale_changed(self) -> None:
        if not self.get_mapped():
            return
        self._apply_look_classes()
        self.apply_theme()
        self.position_window()
        self._relayout_backdrop()

    def _start_osk_watch(self) -> None:
        from ulauncher.modes.launcher.osk import OskWatcher, next_osk_watch_action

        if getattr(self, "_osk_watch", None) is None:
            self._osk_watch = OskWatcher(self._on_osk_changed)
        if next_osk_watch_action(self._osk_watch.listening, True) == "start":
            self._osk_watch.start()
            self._osk_visible = bool(self._osk_watch.visible)
            if self._osk_visible:
                self._raise_input_chrome()
                self.position_window()

    def _stop_osk_watch(self) -> None:
        from ulauncher.modes.launcher.osk import next_osk_watch_action

        watcher = getattr(self, "_osk_watch", None)
        if watcher is None:
            return
        if next_osk_watch_action(watcher.listening, False) == "stop":
            watcher.stop()

    def _on_osk_changed(self, visible: bool) -> None:
        self._osk_visible = bool(visible)
        if visible:
            self._raise_input_chrome()
        else:
            self._sync_input_chrome_layer()
        if self.get_mapped():
            self.position_window()

    def _start_limits_timer(self) -> None:
        from ulauncher.modes.launcher.time_limits import seconds_until_limit
        from ulauncher.utils import scheduling

        self._stop_limits_timer()
        remaining = seconds_until_limit()
        if remaining is None:
            return
        if remaining <= 0:
            self.get_app().close_launcher()
            return
        self._limits_timer = scheduling.timer(remaining, lambda: self.get_app().close_launcher())

    def _stop_limits_timer(self) -> None:
        timer = getattr(self, "_limits_timer", None)
        if timer is None:
            return
        timer.cancel()
        self._limits_timer = None

    def _start_session_watch(self) -> None:
        from ulauncher.modes.launcher.session_watch import SessionWatcher, next_session_watch_action

        if getattr(self, "_session_watch", None) is None:
            self._session_watch = SessionWatcher(lambda: self.get_app().close_launcher())
        if next_session_watch_action(self._session_watch.listening, True) == "start":
            self._session_watch.start()

    def _stop_session_watch(self) -> None:
        from ulauncher.modes.launcher.session_watch import next_session_watch_action

        watcher = getattr(self, "_session_watch", None)
        if watcher is None:
            return
        if next_session_watch_action(watcher.listening, False) == "stop":
            watcher.stop()

    def _stop_live_search(self) -> None:
        from ulauncher.modes.launcher.search_live import next_live_search_action

        watcher = getattr(self, "_live_search", None)
        if watcher is None:
            return
        if next_live_search_action(watcher.listening, False) == "stop":
            watcher.stop()
        idle = getattr(self, "_live_idle", None)
        if idle:
            idle.cancel()
            self._live_idle = None

    def _on_live_search_change(self) -> None:
        from ulauncher.modes.launcher.async_paint import should_schedule_async_paint

        if not should_schedule_async_paint(bool(getattr(self, "_live_idle", None)), self.get_mapped()):
            return
        self._live_idle = scheduling.run_when_idle(self._run_live_repaint)

    def _run_live_repaint(self) -> None:
        from ulauncher.modes.launcher.async_paint import should_run_async_paint

        self._live_idle = None
        if should_run_async_paint(True, self.get_mapped()):
            self.get_app().query_changed(self.prompt_input.get_text())

    def close(self, save_query: bool = False) -> None:  # type: ignore[override]
        logger.info("Closing %s window", app_display_name)
        from ulauncher.modes.launcher.popup_gate import run_isolated_teardown

        self._cancel_live_layout()
        self._cancel_input_chrome_idle()
        self._cancel_refocus_idle()
        # hide before host disconnects so a throw cannot leave visible true
        if self.get_visible():
            self.set_visible(False)
        self._destroy_backdrop()
        self._apply_unredirect(False)
        run_isolated_teardown(
            (
                self._stop_live_search,
                self._stop_session_watch,
                self._stop_osk_watch,
                self._stop_limits_timer,
            )
        )
        if not save_query or not self.settings.auto_resume:
            self.get_app().set_query("", update_input=False)
        if self.settings.grab_mouse_pointer:
            self.toggle_grab_pointer_device(False)
        super().close()
        self.destroy()

    def _launcher_covers_current_monitor(self) -> bool:
        return DESKTOP_ID == "GNOME" and not IS_X11_COMPATIBLE

    def _backdrop_skip_index(self) -> int | None:
        from ulauncher.modes.launcher.click_outside import overlay_skip_index

        if not self._launcher_covers_current_monitor():
            return overlay_skip_index(covers_current_monitor=False, current_index=None)
        monitor = get_monitor(self.settings.render_on_screen != "default-monitor")
        geometries = get_monitor_geometries()
        current = 0 if geometries else None
        if monitor is not None:
            geo = monitor.get_geometry()
            for index, other in enumerate(geometries):
                if other.x == geo.x and other.y == geo.y and other.width == geo.width and other.height == geo.height:
                    current = index
                    break
        return overlay_skip_index(covers_current_monitor=True, current_index=current)

    def _sync_input_chrome_layer(self, ime_panel: bool | None = None) -> None:
        from ulauncher.modes.launcher.ime import ime_panel_visible
        from ulauncher.modes.launcher.popup_chrome import backdrop_layer_for_input_chrome

        backdrop = getattr(self, "_backdrop", None)
        if backdrop is None:
            return
        if ime_panel is None:
            preedit = _read_entry_preedit(self.prompt_input)
            ime_panel = False if preedit else ime_panel_visible()
        backdrop.set_layer(backdrop_layer_for_input_chrome(bool(self._osk_visible), bool(ime_panel)))

    def _raise_input_chrome(self, ime_panel: bool | None = None) -> None:
        self._sync_input_chrome_layer(ime_panel=ime_panel)
        self._raise_input_chrome_soon()

    def _raise_input_chrome_soon(self) -> None:
        from ulauncher.modes.launcher.popup_chrome import should_schedule_input_chrome_raise

        pending = getattr(self, "_input_chrome_idle", None)
        if not should_schedule_input_chrome_raise(pending is not None, self.get_mapped()):
            return
        self._input_chrome_idle = scheduling.run_when_idle(self._run_input_chrome_raise)

    def _run_input_chrome_raise(self) -> None:
        from ulauncher.modes.launcher.popup_chrome import should_raise_on_input_chrome_allocation

        self._input_chrome_idle = None
        if should_raise_on_input_chrome_allocation(self.get_mapped(), True):
            self._sync_input_chrome_layer()

    def _cancel_input_chrome_idle(self) -> None:
        idle = getattr(self, "_input_chrome_idle", None)
        if idle is None:
            return
        idle.cancel()
        self._input_chrome_idle = None

    def _gtk_unredirect_backend(self) -> str:
        from ulauncher.modes.launcher.unredirect import gtk_unredirect_backend, hyprland_session_active

        return gtk_unredirect_backend(self._mutter_has_unredirect_key(), hyprland_session_active())

    def _mutter_has_unredirect_key(self) -> bool:
        from ulauncher.gi import Gio, GLib
        from ulauncher.modes.launcher.unredirect import MUTTER_KEY, MUTTER_SCHEMA

        try:
            source = Gio.SettingsSchemaSource.get_default()
            schema = source.lookup(MUTTER_SCHEMA, True) if source else None
            has_key = getattr(schema, "has_key", None) if schema is not None else None
            return bool(callable(has_key) and has_key(MUTTER_KEY))
        except (GLib.GError, AttributeError, TypeError, RuntimeError, OSError):
            return False

    def _apply_unredirect(self, want_held: bool) -> None:
        from ulauncher.modes.launcher.unredirect import next_unredirect_action

        backend = self._gtk_unredirect_backend()
        action = next_unredirect_action(bool(getattr(self, "_unredirect_held", False)), want_held, backend)
        if action == "hold":
            self._hold_unredirect(backend)
        elif action == "release":
            self._release_unredirect(backend)

    def _hold_unredirect(self, backend: str) -> None:
        from ulauncher.modes.launcher.unredirect import mutter_hold_write

        if backend == "mutter-gsettings":
            settings = self._mutter_unredirect_settings()
            if settings is None:
                return
            previous = bool(settings.get_boolean(self._mutter_unredirect_key()))
            settings.set_boolean(self._mutter_unredirect_key(), mutter_hold_write())
            self._unredirect_restore = previous
            self._unredirect_held = True
            return
        if backend == "hyprland":
            from ulauncher.modes.launcher.unredirect import (
                hyprland_getoption_argv,
                hyprland_hold_argv,
                parse_hyprland_scanout,
            )

            previous = parse_hyprland_scanout(self._run_unredirect_argv(hyprland_getoption_argv()))
            self._run_unredirect_argv(hyprland_hold_argv())
            self._unredirect_restore = previous
            self._unredirect_held = True

    def _release_unredirect(self, backend: str) -> None:
        restore = getattr(self, "_unredirect_restore", None)
        self._unredirect_restore = None
        self._unredirect_held = False
        if backend == "mutter-gsettings" and restore is not None:
            settings = self._mutter_unredirect_settings()
            if settings is not None:
                settings.set_boolean(self._mutter_unredirect_key(), bool(restore))
            return
        if backend == "hyprland":
            from ulauncher.modes.launcher.unredirect import hyprland_restore_argv

            self._run_unredirect_argv(hyprland_restore_argv(str(restore or "")))

    def _mutter_unredirect_key(self) -> str:
        from ulauncher.modes.launcher.unredirect import MUTTER_KEY

        return MUTTER_KEY

    def _mutter_unredirect_settings(self) -> Any:
        from ulauncher.gi import Gio, GLib
        from ulauncher.modes.launcher.unredirect import MUTTER_SCHEMA

        try:
            return Gio.Settings.new(MUTTER_SCHEMA)
        except (GLib.GError, AttributeError, TypeError, RuntimeError, OSError):
            return None

    def _run_unredirect_argv(self, argv: list[str]) -> str:
        import subprocess

        try:
            completed = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return completed.stdout or ""

    def _show_backdrop(self) -> None:
        from ulauncher.ui.backdrop_overlay import PopupBackdrop

        if self._backdrop is None:
            self._backdrop = PopupBackdrop(self._on_backdrop_click, self._raise_over_backdrop)
        self._backdrop.show(self._backdrop_skip_index())
        self._sync_input_chrome_layer(ime_panel=False)

    def _relayout_backdrop(self) -> None:
        backdrop = getattr(self, "_backdrop", None)
        if backdrop is None:
            return
        backdrop.relayout(self._backdrop_skip_index())
        self._sync_input_chrome_layer()
        self.present()

    def _destroy_backdrop(self) -> None:
        idle = getattr(self, "_backdrop_close_idle", None)
        if idle is not None:
            idle.cancel()
            self._backdrop_close_idle = None
        backdrop = getattr(self, "_backdrop", None)
        self._backdrop = None
        if backdrop is not None:
            backdrop.destroy()

    def _on_backdrop_click(self) -> None:
        self.get_app().request_close(save_query=True)

    def _raise_over_backdrop(self) -> None:
        if self.get_visible():
            self.present()
            self.prompt_input.grab_focus()

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
