from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.label_ellipsize import ELLIPSIZE_END, label_ellipsize_spec
from ulauncher.modes.launcher.looks import get_look
from ulauncher.modes.launcher.result_row import NUMBER_HINT_LIMIT, number_hint
from ulauncher.modes.launcher.search_entry import SEARCH_ICON_NAME, SEARCH_ICON_PX, search_entry_spec


def test_label_ellipsize_is_end_fill() -> None:
    spec = label_ellipsize_spec()
    assert spec["ellipsize"] == ELLIPSIZE_END == "end"
    assert spec["single_line"] is True
    assert spec["hexpand"] is True
    assert spec["max_width_chars"] == 1


def test_number_hint_is_digit_for_first_nine_rows() -> None:
    assert number_hint(0, True) == "1"
    assert number_hint(8, True) == "9"
    assert number_hint(9, True) is None
    assert number_hint(0, False) is None
    assert NUMBER_HINT_LIMIT == 9


def test_search_entry_spec_uses_look_hint_and_20px_symbolic_icon() -> None:
    spotlight = search_entry_spec({"look_id": "spotlight", "show_search_icon": True})
    assert spotlight["placeholder"] == get_look("spotlight")["hint"]
    assert spotlight["icon_name"] == SEARCH_ICON_NAME == "system-search-symbolic"
    assert spotlight["icon_px"] == SEARCH_ICON_PX == 20
    assert spotlight["icon_visible"] is True
    assert spotlight["icon_style_class"] == ""

    popos = search_entry_spec(SimpleNamespace(look_id="popos", show_search_icon=True))
    assert popos["placeholder"] == "Type to search"

    hidden = search_entry_spec({"look_id": "tofi", "show_search_icon": False})
    assert hidden["icon_visible"] is False
    assert hidden["icon_style_class"] == "gosh-no-search-icon"
    assert hidden["placeholder"] == get_look("tofi")["hint"]
