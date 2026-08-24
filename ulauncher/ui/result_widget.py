from __future__ import annotations

import logging
from html import unescape
from typing import Callable

from gi.repository import Gtk, Pango

from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
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
    jump_keys: list[str]
    item_box: Gtk.Box
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
        jump_keys: list[str],
        jump_index: int = -1,
    ) -> None:
        self.result = result
        self.query = query
        self._on_select = on_select
        self._on_activate = on_activate
        self.jump_keys = jump_keys
        text_scaling_factor = get_text_scaling_factor()
        from ulauncher.modes.launcher.looks import chrome_from_settings, icon_size_for_look
        from ulauncher.utils.settings import Settings

        chrome = chrome_from_settings(Settings.load())
        icon_size = icon_size_for_look(chrome, str(chrome.get("density") or "comfortable"))
        self._show_numbers = bool(chrome.get("show_numbers"))
        show_icons = bool(chrome.get("show_result_icons", True))
        inner_margin_x = int(12.0 * text_scaling_factor)
        outer_margin_x = int(18.0 * text_scaling_factor)
        margin_y = (3 if result.compact else 5) * text_scaling_factor

        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        gtk4.add_css_class(self, "item-frame")

        click = Gtk.GestureClick()
        click.connect("released", self.on_click)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.on_mouse_hover)
        self.add_controller(motion)

        self.item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(self.item_box, "item-box")
        self.append(self.item_box)
        item_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(item_container, "item-container")
        self.item_box.append(item_container)

        if show_icons:
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
        self.text_container.set_margin_start(inner_margin_x)
        self.text_container.set_margin_end(inner_margin_x)
        gtk4.pack_start(item_container, self.text_container, True, True, 0)

        self.shortcut_label = Gtk.Label(justify=Gtk.Justification.RIGHT, width_request=44)
        gtk4.add_css_class(self.shortcut_label, "item-shortcut")
        gtk4.add_css_class(self.shortcut_label, "item-text")
        gtk4.pack_end(item_container, self.shortcut_label, False, True, 0)

        self.set_index(index if jump_index < 0 else jump_index)
        if not self._show_numbers or not result.highlightable:
            self.shortcut_label.set_visible(False)

        gtk4.add_css_class(item_container, "small-result-item")

        self.title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gtk4.add_css_class(self.title_box, "item-name")
        gtk4.add_css_class(self.title_box, "item-text")

        should_expand = not result.compact and not result.description
        gtk4.pack_start(self.text_container, self.title_box, should_expand, True, 0)

        item_container.set_margin_start(int(outer_margin_x))
        item_container.set_margin_end(int(outer_margin_x))
        item_container.set_margin_top(int(margin_y))
        item_container.set_margin_bottom(int(margin_y))

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
        return Gtk.Label(label=text, hexpand=True, max_width_chars=1, xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)

    def set_index(self, index: int) -> None:
        self.index = index
        if 0 <= index < len(self.jump_keys):
            self.shortcut_label.set_text(f"Alt+{self.jump_keys[index]}")

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
        bottom = allocation.y + allocation.height
        if scroll_y > allocation.y:
            adjustment.set_value(allocation.y)
        elif viewport_height + scroll_y < bottom:
            adjustment.set_value(bottom - viewport_height)

    def highlight_name(self) -> None:
        if self.result.wrap:
            labels = [self._make_text_label(self.result.name)]
        elif (highlightable_input := self.result.get_highlightable_input(str(self.query))) and (
            self.result.searchable or self.result.highlightable
        ):
            labels = []
            for label_text, is_highlight in highlight_text(highlightable_input, self.result.name):
                ellipsize_min = ELLIPSIZE_MIN_LENGTH if not is_highlight else ELLIPSIZE_FORCE_AT_LENGTH
                ellipsize = Pango.EllipsizeMode.MIDDLE if len(label_text) > ellipsize_min else Pango.EllipsizeMode.NONE
                label = Gtk.Label(label=unescape(label_text), ellipsize=ellipsize)
                if is_highlight:
                    gtk4.add_css_class(label, "item-highlight")
                labels.append(label)
        else:
            labels = [Gtk.Label(label=self.result.name, ellipsize=Pango.EllipsizeMode.MIDDLE)]

        expand = self.result.wrap
        for label in labels:
            gtk4.pack_start(self.title_box, label, expand, expand, 0)

    def on_click(self, gesture: Gtk.GestureClick, _n_press: int, _x: float, _y: float) -> None:
        alt = gesture.get_current_button() != 1
        self._on_activate(self.index, alt)

    def on_mouse_hover(self, *_args: object) -> None:
        if self.result.highlightable:
            self._on_select(self.index)
