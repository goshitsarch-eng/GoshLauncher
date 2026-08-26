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


def test_paint_selection_matches_python_result_name() -> None:
    from ulauncher.internals.result import Result

    previous = Result(name="Firefox", highlightable=True, actions={"activate": {"name": "Activate"}})
    rows = [
        Result(name="Chrome", highlightable=True, actions={"activate": {"name": "Activate"}}),
        Result(name="Firefox", highlightable=True, actions={"activate": {"name": "Activate"}}),
    ]
    key = result_selection_key(previous, 0)
    assert key is not None
    assert key["title"] == "Firefox"
    assert paint_selection_index(key, rows) == 1
    assert row_matches_previous(key, rows[1])


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


def test_selection_key_reads_the_kind_and_payload_id() -> None:
    from ulauncher.modes.launcher.results import LauncherResult

    # Result is a dict subclass, so the dict branch used to return early: a LauncherResult has no
    # "id"/"type" key and keeps them in payload/kind, leaving every real row id-less and kindless.
    row = LauncherResult(name="Settings", kind="settings", description="GNOME Settings", payload={"id": "wifi-panel"})
    key = result_selection_key(row, 0)
    assert key is not None
    assert key["type"] == "settings"
    assert key["id"] == "wifi-panel"


def test_repaint_keeps_the_selected_row_when_another_shares_its_title() -> None:
    from ulauncher.modes.launcher.results import LauncherResult

    app = LauncherResult(name="Terminal", kind="app", description="Application", payload={"id": "app:terminal"})
    window = LauncherResult(name="Terminal", kind="window", description="Application", payload={"id": "win:1"})
    key = result_selection_key(app, 1)
    # the repaint reorders them; the highlight has to follow the app row, not the title
    assert paint_selection_index(key, [window, app]) == 1
