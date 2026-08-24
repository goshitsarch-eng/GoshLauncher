from __future__ import annotations

from ulauncher.modes.launcher.bookmarks import normalize_bookmark_uri, parse_gtk_bookmarks
from ulauncher.modes.launcher.paths import (
    canonicalize_launch_uri,
    file_uri_from_absolute,
    match_path,
    path_from_file_uri,
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


def test_match_path_missing_keeps_row() -> None:
    hit = match_path("/no/such/ulauncher/path/here")
    assert hit is not None
    assert hit["exists"] is False
    assert hit["description"] == "Path not found"


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
