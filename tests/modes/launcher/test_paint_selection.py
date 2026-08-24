from __future__ import annotations

from ulauncher.modes.launcher.paint_selection import (
    first_selectable_index,
    paint_selection_index,
    result_selection_key,
    row_matches_previous,
)


def test_paint_selection_keeps_id_and_clamps_missing_rows() -> None:
    keep_rows = [
        {"type": "app", "title": "Firefox", "description": ""},
        {"type": "window", "title": "Firefox", "description": "Workspace 2"},
        {"type": "file", "title": "notes.txt", "description": "~"},
    ]
    assert paint_selection_index(None, keep_rows) == 0
    assert (
        paint_selection_index(
            {"type": "window", "title": "Firefox", "description": "Workspace 2", "index": 1},
            keep_rows,
        )
        == 1
    )
    assert paint_selection_index({"type": "file", "title": "gone.txt", "description": "~", "index": 2}, keep_rows) == 2
    assert paint_selection_index({"type": "file", "title": "gone.txt", "index": 9}, keep_rows) == 0
    assert paint_selection_index({"type": "app", "title": "Firefox"}, []) == -1


def test_paint_selection_prefers_id_over_duplicate_titles() -> None:
    rows = [
        {"type": "window", "title": "Switch to Workspace 2", "id": 7},
        {"type": "workspace", "title": "Switch to Workspace 2", "id": "workspace:2"},
    ]
    assert (
        paint_selection_index(
            {"type": "workspace", "title": "Switch to Workspace 2", "id": "workspace:2", "index": 0},
            rows,
        )
        == 1
    )
    assert (
        paint_selection_index(
            {"type": "window", "title": "Firefox", "description": "Workspace 1", "id": 42, "index": 0},
            [
                {"type": "window", "title": "Firefox", "description": "Workspace 1", "id": 7},
                {"type": "window", "title": "Firefox", "description": "Workspace 2", "id": 42},
            ],
        )
        == 1
    )


def test_first_selectable_skips_pending() -> None:
    assert (
        first_selectable_index(
            [
                {"type": "path", "title": "~/docs", "activatable": False},
                {"type": "path", "title": "Open in Terminal"},
            ]
        )
        == 1
    )
    assert first_selectable_index([{"type": "path", "title": "~/docs", "activatable": False}]) == -1
    key = result_selection_key({"type": "window", "title": "Firefox", "id": 42}, 1)
    assert key is not None
    assert key["id"] == 42
    assert row_matches_previous(key, {"type": "window", "title": "Firefox", "id": 42})
    assert not row_matches_previous(key, {"type": "window", "title": "Firefox", "id": 7})
