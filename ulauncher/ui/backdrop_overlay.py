"""Fullscreen click-outside overlays, ported from spotlight-goshos popupBackdrop.js."""

from __future__ import annotations

from typing import Any, Callable

from gi.repository import Gdk, Gtk

from ulauncher.modes.launcher.click_outside import (
    backdrop_claims_event,
    backdrop_should_close,
    backdrop_teardown_order,
    overlay_plan,
    overlay_window_style,
)
from ulauncher.modes.launcher.popup_gate import run_isolated_teardown
from ulauncher.ui import gtk4
from ulauncher.ui.helpers import layer_shell
from ulauncher.ui.helpers.monitor import get_monitor_geometries

_BACKDROP_CSS = """
window.goshos-backdrop {
  background-color: rgba(0, 0, 0, 0.01);
}
"""


class PopupBackdrop:
    """Transparent windows covering every monitor so a click outside the card closes the popup."""

    def __init__(
        self,
        on_click_outside: Callable[[], None],
        on_became_active: Callable[[], None] | None = None,
    ) -> None:
        self._on_click_outside = on_click_outside
        self._on_became_active = on_became_active
        self._windows: list[Gtk.Window] = []
        self._connections: list[tuple[Any, int]] = []
        self._css = gtk4.load_css_provider(_BACKDROP_CSS)
        self._style = overlay_window_style()

    def window_count(self) -> int:
        return len(self._windows)

    def show(self, skip_index: int | None = None) -> None:
        self.destroy()
        geometries = get_monitor_geometries()
        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display is not None else None
        for item in overlay_plan(geometries, skip_index):
            monitor = monitors.get_item(int(item["index"])) if monitors is not None else None
            window = self._make_window(monitor)
            self._windows.append(window)
            window.present()

    def relayout(self, skip_index: int | None = None) -> None:
        if not self._windows:
            return
        self.show(skip_index)

    def set_layer(self, name: str) -> None:
        for window in self._windows:
            layer_shell.set_layer(window, name)

    def destroy(self) -> None:
        steps = {
            "disconnect": self._disconnect,
            "hide": self._hide,
            "remove-chrome": self._remove_chrome,
            "destroy": self._destroy_windows,
        }
        run_isolated_teardown(steps[name] for name in backdrop_teardown_order())

    def _make_window(self, monitor: Gdk.Monitor | None) -> Gtk.Window:
        window = Gtk.Window(deletable=False, resizable=False, title="")
        window.set_decorated(False)
        window.set_can_focus(bool(self._style["can_focus"]))
        window.set_focusable(False)
        gtk4.add_css_class(window, str(self._style["css_class"]))
        gtk4.add_provider_to_widget(window, self._css)
        window.set_child(Gtk.Box())

        gesture = Gtk.GestureClick()
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.set_button(0)
        press_id = gesture.connect("pressed", self._on_pressed)
        release_id = gesture.connect("released", self._on_released)
        window.add_controller(gesture)
        active_id = window.connect("notify::is-active", self._on_active)
        close_id = window.connect("close-request", self._on_close_request)
        self._connections.extend(((gesture, press_id), (gesture, release_id), (window, active_id), (window, close_id)))

        used_layer = layer_shell.enable_input_only(window, monitor)
        if not used_layer:
            fullscreen_on = getattr(window, "fullscreen_on_monitor", None)
            if callable(fullscreen_on) and monitor is not None:
                fullscreen_on(monitor)
            else:
                window.fullscreen()
        return window

    def _on_pressed(self, gesture: Gtk.GestureClick, *_args: Any) -> None:
        if backdrop_claims_event("button-press"):
            state = getattr(Gtk, "EventSequenceState", None)
            if state is not None:
                gesture.set_state(state.CLAIMED)

    def _on_released(self, _gesture: Gtk.GestureClick, *_args: Any) -> None:
        if backdrop_should_close("button-release"):
            self._on_click_outside()

    def _on_active(self, window: Gtk.Window, *_args: Any) -> None:
        if self._on_became_active is not None and window.is_active():
            self._on_became_active()

    def _on_close_request(self, *_args: Any) -> bool:
        self._on_click_outside()
        return True

    def _disconnect(self) -> None:
        for target, handler_id in self._connections:
            target.disconnect(handler_id)
        self._connections.clear()

    def _hide(self) -> None:
        for window in self._windows:
            window.set_visible(False)

    def _remove_chrome(self) -> None:
        return

    def _destroy_windows(self) -> None:
        for window in self._windows:
            window.destroy()
        self._windows.clear()
