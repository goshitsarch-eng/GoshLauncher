from __future__ import annotations

from ulauncher.modes.launcher.selection_math import is_selectable_result, next_activatable_index, next_selected_index


def test_arrow_wraps_and_page_clamps() -> None:
    assert next_selected_index(0, -1, 5) == 4
    assert next_selected_index(4, 1, 5) == 0
    assert next_selected_index(0, 5, 3) == 2
    assert next_selected_index(2, -5, 3) == 0
    assert next_selected_index(0, 1, 0) == -1
    assert next_selected_index(3, -999, 6) == 0
    assert next_selected_index(1, 999, 6) == 5


def test_arrows_skip_pending_and_page_stays_on_ready() -> None:
    pending_rows = [
        {"title": "checking", "activatable": False},
        {"title": "ready"},
        {"title": "missing", "activatable": False},
    ]
    assert next_activatable_index(-1, 1, pending_rows) == 1
    assert next_activatable_index(1, 1, pending_rows) == 1
    assert next_activatable_index(1, -1, pending_rows) == 1
    assert next_activatable_index(1, 5, pending_rows) == 1
    assert next_activatable_index(-1, 1, [{"activatable": False}]) == -1


def test_page_up_walks_full_list_not_ready_slots() -> None:
    rows = [{"activatable": False} for _ in range(10)]
    rows[0] = {"title": "a"}
    rows[1] = {"title": "b"}
    rows[9] = {"title": "z"}
    # clamp 9 + (-5) onto index 4, then walk back to the nearest ready row
    assert next_activatable_index(9, -5, rows) == 1


def test_python_result_pending_is_not_selectable() -> None:
    class Row:
        def __init__(self, highlightable: bool, actions: dict) -> None:
            self.highlightable = highlightable
            self.actions = actions

    assert is_selectable_result(Row(True, {})) is False
    assert is_selectable_result(Row(False, {"activate": {"name": "Activate"}})) is False
    assert is_selectable_result(Row(True, {"activate": {"name": "Activate"}})) is True
