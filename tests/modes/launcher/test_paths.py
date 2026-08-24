from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher.bookmarks import (
    ensure_bookmarks,
    flush_bookmarks_lookup,
    invalidate_bookmarks,
    normalize_bookmark_uri,
    parse_gtk_bookmarks,
    search_bookmarks,
)
from ulauncher.modes.launcher.paths import (
    canonicalize_launch_uri,
    ensure_path,
    file_uri_from_absolute,
    flush_path_lookup,
    invalidate_path_lookup,
    match_path,
    path_from_file_uri,
    path_row_meta,
    search_path,
    terminal_command,
    terminal_row_meta,
)


def test_file_uri_round_trip() -> None:
    path = "/tmp/My Documents/file name.txt"
    uri = file_uri_from_absolute(path)
    assert " " not in uri
    assert path_from_file_uri(uri) == path


def test_canonicalize_launch_uri_blocks_unsafe_schemes() -> None:
    assert canonicalize_launch_uri("javascript:alert(1)") == ""
    assert canonicalize_launch_uri("data:text/html,hi") == ""
    assert canonicalize_launch_uri("vbscript:msgbox") == ""
    assert canonicalize_launch_uri("java\u200bscript:alert(1)") == ""


def test_match_path_missing_keeps_row() -> None:
    hit = match_path("/no/such/ulauncher/path/here")
    assert hit is not None
    assert hit["exists"] is False
    assert hit["description"] == "Path not found"


def test_path_row_meta_pending_and_ready() -> None:
    pending = path_row_meta("~/code", "/home/me/code", "pending", home="/home/me")
    assert pending["description"] == "Checking path"
    assert pending["checking"] is True
    assert pending["exists"] is False
    missing = path_row_meta("/missing", "/missing", "missing")
    assert missing["description"] == "Path not found"
    ready = path_row_meta("/tmp", "/tmp", "directory")
    assert ready["description"] == "Open path"
    assert ready["exists"] is True


def test_search_path_pending_then_flush_resolves() -> None:
    invalidate_path_lookup()
    rows = search_path("/tmp")
    assert rows
    assert rows[0]["description"] == "Checking path"
    ensure_path("/tmp", lambda: None)
    flush_path_lookup()
    resolved = search_path("/tmp")
    assert resolved[0]["description"] == "Open path"
    assert resolved[0]["exists"] is True


def test_terminal_command_xdg_uses_cwd() -> None:
    cmd = terminal_command("/tmp", find_in_path=lambda name: name if name == "xdg-terminal-exec" else None)
    assert cmd == {"argv": ["xdg-terminal-exec"], "cwd": "/tmp"}


def test_terminal_command_kitty_flag() -> None:
    cmd = terminal_command("/tmp", find_in_path=lambda name: name if name == "kitty" else None)
    assert cmd is not None
    assert cmd["argv"] == ["kitty", "--directory=/tmp"]
    assert cmd["cwd"] is None


def test_terminal_row_meta() -> None:
    row = terminal_row_meta("/home/me/code", home="/home/me")
    assert row["title"] == "Open in Terminal"
    assert row["in_terminal"] is True
    assert row["description"] == "~/code"


def test_bookmark_uri_canonicalizes_and_rejects_unsafe() -> None:
    assert normalize_bookmark_uri("javascript:alert(1)") == ""
    uri = normalize_bookmark_uri("/tmp/My Files")
    assert uri.startswith("file://")
    assert " " not in uri
    rows = parse_gtk_bookmarks("file:///tmp/docs Documents\njavascript:alert(1) bad\n")
    assert [row["title"] for row in rows] == ["Documents"]


def test_search_bookmarks_empty_until_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bookmark_file = tmp_path / "bookmarks"
    bookmark_file.write_text("file:///tmp UniqueBookmarkLabelXYZ\n", encoding="utf-8")
    monkeypatch.setattr("ulauncher.modes.launcher.bookmarks.BOOKMARK_FILES", (bookmark_file,))
    invalidate_bookmarks()
    assert search_bookmarks("UniqueBookmarkLabelXYZ") == []
    ensure_bookmarks(lambda: None)
    flush_bookmarks_lookup()
    rows = search_bookmarks("UniqueBookmarkLabelXYZ")
    assert rows
    assert rows[0]["title"] == "UniqueBookmarkLabelXYZ"
