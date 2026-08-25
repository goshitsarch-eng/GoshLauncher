from __future__ import annotations

import logging
from html import unescape
from typing import Callable

from gi.repository import Gtk, Pango

from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.modes.launcher.scroll_view import scroll_value_to_show_row
from ulauncher.ui import gtk4
from ulauncher.ui.helpers.monitor import get_text_scaling_factor
from ulauncher.ui.helpers.text_highlighter import highlight_text
from ulauncher.ui.load_icon_surface import load_icon_paintable

ELLIPSIZE_MIN_LENGTH = 6
ELLIPSIZE_FORCE_AT_LENGTH = 20
logger = logging.getLogger(__name__)


class ResultWidget(Gtk.Box):
    index: int = 0
    query: Query
    result: Result
    item_box: Gtk.Box
    item_container: Gtk.Box
    shortcut_label: Gtk.Label
    title_box: Gtk.Box
    text_container: Gtk.Box

    def __init__(  # noqa: PLR0915
        self,
        result: Result,
        index: int,
        query: Query,
        on_select: Callable[[int], None],
        on_activate: Callable[[int, bool], None],
        jump_index: int = -1,
    ) -> None:
        self.result = result
        self.query = query
        self._on_select = on_select
        self._on_activate = on_activate
        self.widget_index = index
        text_scaling_factor = get_text_scaling_factor()
        from ulauncher.modes.launcher.looks import chrome_from_settings, icon_size_for_look
        from ulauncher.modes.launcher.result_row import RESULT_CHILD_SPACING
        from ulauncher.utils.settings import Settings

        chrome = chrome_from_settings(Settings.load())
        icon_size = icon_size_for_look(chrome, str(chrome.get("density") or "comfortable"))
        self._show_numbers = bool(chrome.get("show_numbers"))
        show_icons = bool(chrome.get("show_result_icons", True))

        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        gtk4.add_css_class(self, "item-frame")
        self.set_can_focus(False)
        self._pointer_pressed = False
        self._touch_start_y = None
        self._touch_dragged = False

        click = Gtk.GestureClick()
        click.connect("pressed", self.on_pointer_press)
        click.connect("released", self.on_click)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.on_mouse_hover)
        motion.connect("leave", self.on_pointer_leave)
        self.add_controller(motion)
        legacy = getattr(Gtk, "EventControllerLegacy", None)
        if legacy is not None:
            touch = legacy()
            touch.connect("event", self.on_touch_event)
            self.add_controller(touch)

        self.item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(self.item_box, "item-box")
        self.append(self.item_box)
        item_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=RESULT_CHILD_SPACING)
        gtk4.add_css_class(item_container, "item-container")
        self.item_box.append(item_container)
        self.item_container = item_container

        from ulauncher.modes.launcher.result_icon import should_build_result_icon

        if should_build_result_icon(show_icons):
            icon = Gtk.Image()
            icon.set_from_paintable(
                load_icon_paintable(result.icon or "image-missing", icon_size, self.get_scale_factor())
            )
            gtk4.add_css_class(icon, "item-icon")
            gtk4.pack_start(item_container, icon, False, True, 0)

        self.text_container = Gtk.Box(
            width_request=int(350.0 * text_scaling_factor),
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
        )
        gtk4.pack_start(item_container, self.text_container, True, True, 0)

        self.shortcut_label = Gtk.Label(justify=Gtk.Justification.RIGHT, width_request=44)
        gtk4.add_css_class(self.shortcut_label, "item-shortcut")
        gtk4.add_css_class(self.shortcut_label, "item-text")
        gtk4.pack_end(item_container, self.shortcut_label, False, True, 0)

        self.set_index(index if jump_index < 0 else jump_index)
        if not result.highlightable or not self.shortcut_label.get_text():
            self.shortcut_label.set_visible(False)

        gtk4.add_css_class(item_container, "small-result-item")

        self.title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(self.title_box, "item-name")
        gtk4.add_css_class(self.title_box, "item-text")

        should_expand = not result.compact and not result.description
        gtk4.pack_start(self.text_container, self.title_box, should_expand, True, 0)

        if result.description and not result.compact:
            descr_label = self._make_text_label()
            gtk4.add_css_class(descr_label, "item-descr")
            gtk4.add_css_class(descr_label, "item-text")
            descr_label.set_text(unescape(result.description))
            gtk4.pack_start(self.text_container, descr_label, False, True, 0)
        self.highlight_name()
        if not result.highlightable:
            self.shortcut_label.set_visible(False)
            gtk4.add_css_class(self, "item-header")

    def _make_text_label(self, text: str = "") -> Gtk.Label:
        if self.result.wrap:
            return Gtk.Label(label=text, hexpand=True, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        from ulauncher.modes.launcher.label_ellipsize import label_ellipsize_spec

        spec = label_ellipsize_spec()
        label = Gtk.Label(
            label=text,
            hexpand=spec["hexpand"],
            max_width_chars=spec["max_width_chars"],
            xalign=0,
            ellipsize=Pango.EllipsizeMode.END,
        )
        label.set_single_line_mode(spec["single_line"])
        return label

    def set_index(self, index: int) -> None:
        from ulauncher.modes.launcher.result_row import number_hint

        self.index = index
        hint = number_hint(index, self._show_numbers)
        self.shortcut_label.set_text(hint or "")

    def select(self) -> None:
        gtk4.add_css_class(self.item_box, "selected")
        self.scroll_to_focus()

    def deselect(self) -> None:
        gtk4.remove_css_class(self.item_box, "selected")

    def scroll_to_focus(self) -> None:
        scrolled = self.get_ancestor(Gtk.ScrolledWindow)
        if not isinstance(scrolled, Gtk.ScrolledWindow):
            return
        adjustment = scrolled.get_vadjustment()
        viewport_height = scrolled.get_allocated_height()
        scroll_y = adjustment.get_value()
        allocation = self.get_allocation()
        # page_size is 0 before the first allocate; writing that offset jumps the list
        adjustment.set_value(scroll_value_to_show_row(allocation.y, allocation.height, scroll_y, viewport_height))

    def highlight_name(self) -> None:
        if self.result.wrap:
            labels = [self._make_text_label(self.result.name)]
        elif (highlightable_input := self.result.get_highlightable_input(str(self.query))) and (
            self.result.searchable or self.result.highlightable
        ):
            labels = []
            for label_text, is_highlight in highlight_text(highlightable_input, self.result.name):
                ellipsize_min = ELLIPSIZE_MIN_LENGTH if not is_highlight else ELLIPSIZE_FORCE_AT_LENGTH
                ellipsize = Pango.EllipsizeMode.END if len(label_text) > ellipsize_min else Pango.EllipsizeMode.NONE
                label = Gtk.Label(
                    label=unescape(label_text),
                    ellipsize=ellipsize,
                    hexpand=True,
                    max_width_chars=1,
                    xalign=0,
                )
                if ellipsize != Pango.EllipsizeMode.NONE:
                    label.set_single_line_mode(True)
                if is_highlight:
                    gtk4.add_css_class(label, "item-highlight")
                labels.append(label)
        else:
            labels = [self._make_text_label(self.result.name)]

        expand = self.result.wrap
        for label in labels:
            gtk4.pack_start(self.title_box, label, expand, expand, 0)

    def _pointer_from_touchscreen(self, gesture: Gtk.Gesture) -> bool:
        from ulauncher.modes.launcher.result_pointer import device_is_touchscreen

        device = gesture.get_device()
        getter = getattr(device, "get_source", None) if device is not None else None
        return device_is_touchscreen(getter() if callable(getter) else "")

    def on_pointer_press(self, gesture: Gtk.GestureClick, _n_press: int, _x: float, _y: float) -> None:
        from ulauncher.modes.launcher.result_pointer import row_pointer_action, should_ignore_pointer_for_touch

        if should_ignore_pointer_for_touch(self._pointer_from_touchscreen(gesture)):
            return
        action = row_pointer_action("press", gesture.get_current_button(), self._pointer_pressed)
        self._pointer_pressed = bool(action["pressed"])
        if action["action"] == "stop":
            state = getattr(Gtk, "EventSequenceState", None)
            if state is not None:
                gesture.set_state(state.CLAIMED)

    def on_click(self, gesture: Gtk.GestureClick, _n_press: int, _x: float, _y: float) -> None:
        from ulauncher.modes.launcher.result_pointer import (
            PRIMARY_BUTTON,
            row_pointer_action,
            should_ignore_pointer_for_touch,
        )

        if should_ignore_pointer_for_touch(self._pointer_from_touchscreen(gesture)):
            return
        button = gesture.get_current_button()
        action = row_pointer_action("release", button, self._pointer_pressed)
        self._pointer_pressed = bool(action["pressed"])
        if action["action"] != "activate":
            return
        alt = button != PRIMARY_BUTTON
        self._on_activate(self.widget_index, alt)

    def on_pointer_leave(self, *_args: object) -> None:
        from ulauncher.modes.launcher.result_pointer import PRIMARY_BUTTON, row_pointer_action

        action = row_pointer_action("leave", PRIMARY_BUTTON, self._pointer_pressed)
        self._pointer_pressed = bool(action["pressed"])
        self._touch_start_y = None
        self._touch_dragged = False

    def on_touch_event(self, _controller: object, event: object) -> bool:
        from ulauncher.modes.launcher.result_pointer import (
            event_y,
            next_row_touch_state,
            touch_kind_from_event_type,
        )

        getter = getattr(event, "get_event_type", None)
        kind = touch_kind_from_event_type(getter() if callable(getter) else "")
        if kind is None:
            return False
        state = next_row_touch_state(
            kind,
            event_y(event),
            self._touch_start_y,
            self._pointer_pressed,
            self._touch_dragged,
        )
        self._touch_start_y = state["start_y"]
        self._pointer_pressed = bool(state["pressed"])
        self._touch_dragged = bool(state["dragged"])
        if state["action"] == "activate":
            self._on_activate(self.widget_index, False)
        return False

    def on_mouse_hover(self, *_args: object) -> None:
        parent = self.get_ancestor(Gtk.ScrolledWindow)
        hover_ok = getattr(parent, "hover_allowed", None)
        if callable(hover_ok) and not hover_ok():
            return
        if self.result.highlightable:
            self._on_select(self.widget_index)
