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
    canonicalize_file_uri,
    canonicalize_launch_uri,
    canonicalize_remote_uri,
    decode_uri_component_safe,
    ensure_path,
    file_uri_from_absolute,
    flush_path_lookup,
    invalidate_path_lookup,
    match_path,
    path_from_file_uri,
    path_row_meta,
    path_rows,
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
    assert pending["type"] == "path"
    assert pending["id"] == "/home/me/code"
    assert pending["activatable"] is False
    missing = path_row_meta("/missing", "/missing", "missing")
    assert missing["description"] == "Path not found"
    assert missing["activatable"] is False
    ready = path_row_meta("/tmp", "/tmp", "directory")
    assert ready["description"] == "Open path"
    assert ready["exists"] is True
    assert ready["id"] == "/tmp"
    assert "activatable" not in ready
    pdf = path_row_meta("notes.pdf", "/tmp/notes.pdf", "file")
    assert pdf["icon"] == "x-office-document-symbolic"
    png = path_row_meta("shot.png", "/home/me/shot.png", "file", home="/home/me")
    assert png["icon"] == "image-x-generic-symbolic"


def test_goshos_latin1_percent_decode_stays_raw() -> None:
    # JS decodeURIComponent throws on latin-1 percent bytes; Python unquote must not
    # replace them or canonicalize_file_uri re-encodes a replacement character.
    assert decode_uri_component_safe("caf%E9") == "caf%E9"
    assert decode_uri_component_safe("My%20File") == "My File"
    assert path_from_file_uri("file:///home/u/caf%E9") == ""
    assert canonicalize_file_uri("file:///home/u/caf%E9") == "file:///home/u/caf%E9"
    assert canonicalize_remote_uri("sftp://nas/caf%E9") == "sftp://nas/caf%E9"


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
    assert row["id"] == "terminal:/home/me/code"
    assert row["type"] == "path"
    assert row["description"] == "~/code"
    place = terminal_row_meta("/home/me/docs", home="/home/me", kind="place")
    assert place["type"] == "place"


def test_path_rows_omit_terminal_when_missing() -> None:
    missing = path_rows("/tmp", "/tmp", "directory", find_in_path=lambda _name: None)
    assert len(missing) == 1
    assert missing[0].get("in_terminal") is False
    present = path_rows(
        "/tmp",
        "/tmp",
        "directory",
        find_in_path=lambda name: name if name == "xdg-terminal-exec" else None,
    )
    assert present[1]["title"] == "Open in Terminal"
    assert present[1]["in_terminal"] is True


def test_bookmark_uri_canonicalizes_and_rejects_unsafe() -> None:
    assert normalize_bookmark_uri("javascript:alert(1)") == ""
    assert normalize_bookmark_uri("\u200bjavascript:alert(1)") == ""
    assert normalize_bookmark_uri("DATA:text/html,hi") == ""
    assert normalize_bookmark_uri("FILE:///home/u/x") == "file:///home/u/x"
    uri = normalize_bookmark_uri("/tmp/My Files")
    assert uri.startswith("file://")
    assert " " not in uri
    rows = parse_gtk_bookmarks("file:///tmp/docs Documents\njavascript:alert(1) bad\n")
    assert [row["title"] for row in rows] == ["Documents"]


def test_bookmark_title_and_match_follow_goshos() -> None:
    from ulauncher.modes.launcher.bookmarks import (
        bookmark_description,
        bookmark_icon,
        bookmark_matches,
        bookmark_title,
        host_from_uri,
        match_bookmarks,
        merge_bookmark_files,
    )

    assert host_from_uri("sftp://me@nas.local/share") == "nas.local"
    assert bookmark_title("file:///home/u/Projects", "") == "Projects"
    assert bookmark_title("file:///home/u/Projects", "Code") == "Code"
    assert bookmark_title("sftp://nas/share", "") == "share"
    assert bookmark_description("file:///home/u/Projects", "/home/u") == "~/Projects"
    assert bookmark_icon("file:///tmp") == "folder-symbolic"
    assert bookmark_icon("sftp://nas/share") == "network-server-symbolic"
    assert bookmark_matches("Code", "~/Projects", "cod")
    assert bookmark_matches("Notes", "~/Documents", "doc")
    assert bookmark_matches("Notes", "~/Documents", "notes documents")
    assert not bookmark_matches("Code", "~/Projects", "o")
    assert not bookmark_matches("Code", "/home/u/Projects", "ome")
    merged = merge_bookmark_files(["file:///a A", "file:///a B\nfile:///b B"])
    assert len(merged) == 2
    rows = [{"title": "Code", "description": "~/x"}, {"title": "Zed", "description": "~/z"}]
    assert len(match_bookmarks("z", rows, 2)) == 1
    assert match_bookmarks("z", [{"title": "Zed", "description": "~/z"}], 0) == []


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


def test_terminal_command_fallbacks_match_goshos() -> None:
    ptyxis = terminal_command("/tmp/docs", find_in_path=lambda name: name if name == "ptyxis" else None)
    assert ptyxis is not None
    assert "--working-directory=/tmp/docs" in ptyxis["argv"]
    wezterm = terminal_command("/tmp/docs", find_in_path=lambda name: name if name == "wezterm" else None)
    assert wezterm is not None
    assert wezterm["argv"][:2] == ["wezterm", "start"]
    assert "--cwd=/tmp/docs" in wezterm["argv"]
    ghostty = terminal_command("/tmp/docs", find_in_path=lambda name: name if name == "ghostty" else None)
    assert ghostty is not None
    assert "--working-directory=/tmp/docs" in ghostty["argv"]
    foot = terminal_command("/tmp", find_in_path=lambda name: name if name == "foot" else None)
    assert foot is not None
    assert foot["argv"][0] == "foot"
    tilix = terminal_command("/tmp", find_in_path=lambda name: name if name == "tilix" else None)
    assert tilix is not None
    assert tilix["argv"][0] == "tilix"
    assert terminal_command("/tmp", find_in_path=lambda _name: None) is None
    assert terminal_command("", find_in_path=lambda name: name) is None


def test_expand_home_argv_and_spawn_path() -> None:
    from ulauncher.modes.launcher.paths import expand_home_argv, resolve_command_argv, resolve_spawn_path

    assert expand_home_argv(["./tool", "~/out"], "/home/u") == ["/home/u/tool", "/home/u/out"]
    assert resolve_spawn_path("scripts/deploy", "/home/u") == "/home/u/scripts/deploy"
    assert resolve_spawn_path("ls", "/home/u") == "ls"
    assert resolve_spawn_path("./tool", "/home/u") == "/home/u/tool"
    assert resolve_command_argv(["scripts/deploy", "notes.txt"], "/home/u") == ["/home/u/scripts/deploy", "notes.txt"]


def test_expand_path_collapses_tilde_parent_like_goshos() -> None:
    from ulauncher.modes.launcher.paths import collapse_home, expand_path, normalize_absolute

    assert expand_path("~/bin/x", "/home/u") == "/home/u/bin/x"
    assert expand_path("./run", "/home/u") == "/home/u/run"
    assert expand_path(".", "/home/u") == "/home/u"
    assert expand_path("~", "/home/u") == "/home/u"
    assert expand_path("/usr/bin/ls", "/home/u") == "/usr/bin/ls"
    assert expand_path("ls", "/home/u") == "ls"
    assert expand_path("~/../etc", "/home/u") == "/home/etc"
    assert normalize_absolute("/home/u/../x/./y") == "/home/x/y"
    assert collapse_home("/home/u/docs", "/home/u") == "~/docs"
    assert collapse_home("/home/u", "/home/u") == "~"
    assert collapse_home("/tmp", "/home/u") == "/tmp"
