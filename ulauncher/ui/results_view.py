from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Callable

from gi.repository import Gtk, Pango

from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.modes.launcher.no_results import no_results_detail, no_results_title, should_show_no_results
from ulauncher.modes.launcher.paint_selection import (
    first_selectable_index,
    paint_selection_index,
    result_selection_key,
    row_matches_previous,
)
from ulauncher.modes.launcher.scroll_view import set_overlay_scrollbars
from ulauncher.modes.launcher.selection_math import next_activatable_index
from ulauncher.ui import gtk4
from ulauncher.utils import scheduling

if TYPE_CHECKING:
    from ulauncher.internals.results_update import ResultsUpdate
    from ulauncher.ui.result_widget import ResultWidget
    from ulauncher.utils.settings import Settings

logger = logging.getLogger(__name__)


class ResultsView(Gtk.ScrolledWindow):
    """Scrollable list of results, owning the result widgets and the selection within them."""

    _has_wrapped_results = False
    _index = 0
    _user_selected = False
    _query = ""

    def __init__(
        self,
        settings: Settings,
        apply_css: Callable[[Gtk.Widget], None],
        activate_result: Callable[[bool], None],
    ) -> None:
        super().__init__(
            can_focus=False,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True,
        )
        self._settings = settings
        self._apply_css = apply_css
        self._activate_result = activate_result
        self._chrome: Mapping[str, Any] | None = None
        self._widgets: list[ResultWidget] = []
        self._painting = False
        self._hover_suppressed_until_us = 0
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        gtk4.add_css_class(self._box, "result-box")
        self.set_child(self._box)
        # overlay bars sit on the row and hide Alt+1-9 hints
        set_overlay_scrollbars(self, False)

    @property
    def has_results(self) -> bool:
        return bool(self._highlightable_indices())

    def get_result_objects(self) -> list[Result]:
        return [widget.result for widget in self._widgets]

    @property
    def selected_index(self) -> int:
        return self._index

    def set_max_height(self, height: int) -> None:
        self.set_max_content_height(height)

    def set_chrome(self, chrome: Mapping[str, Any] | None) -> None:
        """Look chrome for new rows. None falls back to Settings.load() in ResultWidget."""
        self._chrome = chrome

    def render(self, update: ResultsUpdate) -> None:
        # goshos keepSelection: prefs and async paints of the same query keep the highlight
        same_query = str(update["query"]) == self._query
        if not same_query:
            self._query = str(update["query"])
            self._user_selected = False

        if update["append"] and self._widgets:
            self._append_results(update)
        else:
            self._replace_results(update, keep_selection=same_query)

    def get_active_result(self) -> Result | None:
        selected = self._selected
        if selected is None:
            return None
        if selected.result.highlightable:
            return selected.result
        highlightable = self._highlightable_indices()
        if highlightable:
            return self._widgets[highlightable[0]].result
        return None

    def select(self, index: int) -> None:
        self._select(index)
        self._user_selected = True

    def numbered_results(self) -> list[Result]:
        """Rows that carry 1-9 hints. Headers are not in this list, matching goshos."""
        return [self._widgets[index].result for index in self._highlightable_indices()]

    def select_jump(self, jump_index: int) -> None:
        highlightable = self._highlightable_indices()
        if 0 <= jump_index < len(highlightable):
            self.select(highlightable[jump_index])

    def go_up(self) -> None:
        self._move(-1)

    def go_down(self) -> None:
        self._move(1)

    def go_page_up(self) -> None:
        self._move(-5)

    def go_page_down(self) -> None:
        self._move(5)

    def go_home(self) -> None:
        self._move(-999)

    def go_end(self) -> None:
        self._move(999)

    def suppress_hover(self, duration_us: int = 150_000) -> None:
        self._hover_suppressed_until_us = time.monotonic_ns() // 1000 + duration_us

    def hover_allowed(self) -> bool:
        from ulauncher.modes.launcher.result_pointer import should_apply_hover_selection

        now = time.monotonic_ns() // 1000
        return should_apply_hover_selection(self._painting, now, self._hover_suppressed_until_us)

    def _move(self, step: int) -> None:
        results = [widget.result for widget in self._widgets]
        nxt = next_activatable_index(self._index, step, results)
        if nxt < 0:
            return
        self.suppress_hover()
        self.select(nxt)

    def _highlightable_indices(self) -> list[int]:
        return [i for i, widget in enumerate(self._widgets) if widget.result.highlightable]

    def _nav_indices(self) -> list[int]:
        return [i for i, widget in enumerate(self._widgets) if widget.result.highlightable and widget.result.actions]

    def _selectable_indices(self) -> list[int]:
        return self._highlightable_indices()

    def _replace_results(self, update: ResultsUpdate, *, keep_selection: bool) -> None:
        self._painting = True
        try:
            previous_index = self._index
            previous_pick = self.get_active_result() if keep_selection else None
            gtk4.remove_all_children(self._box)
            self._widgets = []
            self._index = 0

            result_list = update["results"]
            self._has_wrapped_results = any(result.wrap for result in result_list)
            if not self._has_wrapped_results:
                self.set_min_content_height(-1)

            if not result_list:
                self._user_selected = False
                query_text = str(update["query"])
                if should_show_no_results(query_text, 0):
                    self._show_no_results(query_text)
                else:
                    self.set_visible(False)
                logger.debug("Hiding results container, no results found")
                return

            self._add_widgets(result_list, update["query"], start_index=0)
            self._apply_selection(update["selected_name"], previous_pick, previous_index)
            self._apply_css(self._box)
            gtk4.show_all(self)
            self._fit_results_height()
            logger.debug("Render %s results", len(self._widgets))
        finally:
            self._painting = False

    def _append_results(self, update: ResultsUpdate) -> None:
        existing = len(self._widgets)
        new_results = update["results"]
        if not new_results:
            return
        if any(result.wrap for result in new_results):
            self._has_wrapped_results = True
        self._add_widgets(new_results, update["query"], start_index=existing)
        if not self._user_selected:
            self._apply_selection(update["selected_name"], None)
        self._apply_css(self._box)
        gtk4.show_all(self)
        self._fit_results_height()

    def _add_widgets(self, results: list[Result], query: Query, start_index: int) -> None:
        from ulauncher.ui.result_widget import ResultWidget

        jump_i = len(self._highlightable_indices())
        for offset, result in enumerate(results):
            jump_index = jump_i if result.highlightable else -1
            if jump_index >= 0:
                jump_i += 1
            try:
                widget = ResultWidget(
                    result,
                    start_index + offset,
                    query,
                    self.select,
                    self._select_and_activate,
                    jump_index,
                    chrome=self._chrome,
                )
                self._box.append(widget)
            except Exception:  # noqa: BLE001, S112
                # a bad icon must not leave the list empty
                continue
            self._widgets.append(widget)

    def _select_and_activate(self, index: int, alt: bool) -> None:
        self.select(index)
        self._activate_result(alt)

    def _apply_selection(
        self, selected_name: str | None, previous_pick: Result | None, previous_index: int | None = None
    ) -> None:
        rows = [widget.result for widget in self._widgets]
        if previous_pick:
            key = result_selection_key(previous_pick, self._index if previous_index is None else previous_index)
            index = paint_selection_index(key, rows)
            if index >= 0:
                if not row_matches_previous(key, rows[index]):
                    self._user_selected = False
                # applySelection(skipScroll) — do not mark this as a user arrow
                self._select(index)
                return
            self._user_selected = False
        self._select(self._index_for_name(selected_name))

    def _select(self, index: int) -> None:
        highlightable = self._highlightable_indices()
        if not self._widgets:
            return
        if index not in highlightable:
            first = first_selectable_index([widget.result for widget in self._widgets])
            index = first if first >= 0 else (highlightable[0] if highlightable else 0)
        if self._selected:
            self._selected.deselect()
        self._index = index
        if 0 <= index < len(self._widgets):
            self._widgets[index].select()

    @property
    def _selected(self) -> ResultWidget | None:
        if len(self._widgets) > self._index:
            return self._widgets[self._index]
        return None

    def _index_for_name(self, name: str | None) -> int:
        for index, widget in enumerate(self._widgets):
            if widget.result.searchable and widget.result.name == name:
                return index
        first = first_selectable_index([widget.result for widget in self._widgets])
        if first >= 0:
            return first
        highlightable = self._highlightable_indices()
        return highlightable[0] if highlightable else 0

    def _fit_results_height(self) -> None:
        if not self._has_wrapped_results:
            return
        width = self.get_width()
        if width <= 0:
            scheduling.run_when_idle(self._fit_results_height)
            return
        current_height = self.get_min_content_height()
        max_height = self.get_max_content_height()
        _min_h, needed_height = gtk4.measure_height_for_width(self._box, width)
        if max_height > 0:
            needed_height = min(needed_height, max_height)
        if abs(needed_height - current_height) > 1:
            self.set_min_content_height(needed_height)
            scheduling.run_when_idle(self.queue_resize)

    def _show_no_results(self, query: str) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        gtk4.add_css_class(box, "gosh-no-results")
        title = Gtk.Label(label=no_results_title())
        gtk4.add_css_class(title, "gosh-no-results-title")
        title.set_wrap(True)
        title.set_xalign(0.5)
        detail = Gtk.Label(label=no_results_detail(query))
        from ulauncher.modes.launcher.label_ellipsize import label_ellipsize_spec

        spec = label_ellipsize_spec()
        detail.set_ellipsize(Pango.EllipsizeMode.END)
        detail.set_single_line_mode(spec["single_line"])
        detail.set_hexpand(spec["hexpand"])
        detail.set_max_width_chars(spec["max_width_chars"])
        detail.set_xalign(0.5)
        box.append(title)
        box.append(detail)
        self._box.append(box)
        self._apply_css(self._box)
        gtk4.show_all(self)
        self.set_visible(True)
