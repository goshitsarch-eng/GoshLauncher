from typing import cast
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.ui.result_widget import ResultWidget


def noop(*_args: object) -> None:
    pass


class TestResultWidget:
    @pytest.fixture(autouse=True)
    def scroll_to_focus(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("ulauncher.ui.result_widget.ResultWidget.scroll_to_focus")

    def test_descr(self) -> None:
        assert len(ResultWidget(Result(), 0, Query("", None), noop, noop).text_container.get_children()) == 1
        res = Result(description="descr")
        assert len(ResultWidget(res, 0, Query("", None), noop, noop).text_container.get_children()) == 2
        res = Result(description="descr", compact=True)
        assert len(ResultWidget(res, 0, Query("", None), noop, noop).text_container.get_children()) == 1

    def test_select(self) -> None:
        result_wgt = ResultWidget(Result(), 0, Query("query", None), noop, noop)
        assert not result_wgt.item_box.has_css_class("selected")
        result_wgt.select()
        assert result_wgt.item_box.has_css_class("selected")
        result_wgt.deselect()
        assert not result_wgt.item_box.has_css_class("selected")

    def test_shortcut(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "ulauncher.modes.launcher.looks.chrome_from_settings",
            return_value={"show_numbers": True, "show_result_icons": True, "density": "comfortable", "icon_size": 28},
        )
        result_wgt = ResultWidget(Result(), 0, Query("query", None), noop, noop)
        assert result_wgt.shortcut_label.get_text() == "1"
        result_wgt.set_index(2)
        assert result_wgt.shortcut_label.get_text() == "3"
        result_wgt.set_index(9)
        assert result_wgt.shortcut_label.get_text() == ""

    def test_wrap__name_and_description_labels_wrap_instead_of_ellipsizing(self) -> None:
        from gi.repository import Gtk, Pango

        res = Result(name="long name", description="long descr", wrap=True)
        widget = ResultWidget(res, 0, Query("", None), noop, noop)

        name_label = cast("Gtk.Label", widget.title_box.get_children()[0])
        descr_label = cast("Gtk.Label", widget.text_container.get_children()[1])
        for label in (name_label, descr_label):
            assert label.get_wrap()
            assert label.get_ellipsize() == Pango.EllipsizeMode.NONE

    def test_wrap__defaults_to_single_ellipsized_line(self) -> None:
        from gi.repository import Gtk, Pango

        res = Result(name="long name", description="long descr")
        widget = ResultWidget(res, 0, Query("", None), noop, noop)

        name_label = cast("Gtk.Label", widget.title_box.get_children()[0])
        descr_label = cast("Gtk.Label", widget.text_container.get_children()[1])
        for label in (name_label, descr_label):
            assert not label.get_wrap()
            assert label.get_ellipsize() == Pango.EllipsizeMode.END

    def test_wrap__highlighting_is_skipped(self) -> None:
        from gi.repository import Gtk

        res = Result(name="wrapped name", wrap=True, highlightable=True)
        widget = ResultWidget(res, 0, Query("wrap", None), noop, noop)

        # highlighting would split the name over multiple labels, which cannot wrap as one paragraph
        children = widget.title_box.get_children()
        assert len(children) == 1
        assert cast("Gtk.Label", children[0]).get_text() == "wrapped name"
        assert not any(c.has_css_class("item-highlight") for c in children)

    def test_touch_tap_activates_and_pan_does_not(self) -> None:
        from types import SimpleNamespace

        from ulauncher.modes.launcher.result_pointer import TOUCH_TAP_SLOP

        activated: list[tuple[int, bool]] = []
        widget = ResultWidget(
            Result(),
            0,
            Query("", None),
            noop,
            lambda index, alt: activated.append((index, alt)),
        )

        def event(kind: str, y: float) -> SimpleNamespace:
            return SimpleNamespace(
                get_event_type=lambda: SimpleNamespace(value_nick=kind),
                get_position=lambda: (0.0, y),
            )

        widget.on_touch_event(None, event("touch-begin", 10.0))
        widget.on_touch_event(None, event("touch-end", 12.0))
        assert activated == [(0, False)]

        activated.clear()
        widget.on_touch_event(None, event("touch-begin", 10.0))
        widget.on_touch_event(None, event("touch-update", 10.0 + TOUCH_TAP_SLOP + 4))
        widget.on_touch_event(None, event("touch-end", 10.0 + TOUCH_TAP_SLOP + 4))
        assert activated == []

    def test_look_css_owns_row_padding(self) -> None:
        from ulauncher.modes.launcher.result_row import RESULT_CHILD_SPACING

        widget = ResultWidget(Result(), 0, Query("", None), noop, noop)
        assert widget.item_container.get_spacing() == RESULT_CHILD_SPACING
        assert widget.item_container.get_margin_start() == 0
        assert widget.item_container.get_margin_end() == 0
        assert widget.item_container.get_margin_top() == 0
        assert widget.item_container.get_margin_bottom() == 0
        assert widget.text_container.get_margin_start() == 0
        assert widget.text_container.get_margin_end() == 0
