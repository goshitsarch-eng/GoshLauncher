from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher.recents import (
    basename_from_uri,
    ensure_recent_files,
    flush_recents_lookup,
    icon_for_basename,
    invalidate_recent_files,
    match_recents,
    parse_recent_xbel,
    parse_xbel,
    recent_exists_should_settle,
    search_recents,
    usable_recent_uri,
)


def test_usable_recent_uri_rejects_web_and_script() -> None:
    assert usable_recent_uri("https://example.com/doc") == ""
    assert usable_recent_uri("javascript:alert(1)") == ""
    assert usable_recent_uri("file:javascript:alert(1)") == ""
    assert usable_recent_uri("data:text/plain,hi") == ""
    assert usable_recent_uri("sftp://nas/Public/notes.txt").startswith("sftp://")


def test_parse_xbel_skips_http_and_keeps_remote(tmp_path: Path) -> None:
    notes = tmp_path / "quarterly-report.txt"
    notes.write_text("ok", encoding="utf-8")
    xbel = f"""<?xml version="1.0"?>
<xbel>
  <bookmark href="https://example.com/ignore"/>
  <bookmark href="javascript:alert(1)"/>
  <bookmark href="file:javascript:alert(1)"/>
  <bookmark href="{notes.as_uri()}"/>
  <bookmark href="sftp://office/docs/memo.pdf"/>
</xbel>
"""
    rows = parse_xbel(xbel)
    titles = [row["title"] for row in rows]
    assert "quarterly-report.txt" in titles
    assert "memo.pdf" in titles
    assert all("example.com" not in row["uri"] for row in rows)


def test_match_recents_parent_folder_and_multi_word() -> None:
    rows = [
        {
            "uri": "file:///home/user/Documents/quarterly-report.txt",
            "title": "quarterly-report.txt",
            "description": "~/Documents",
            "icon": "text-x-generic",
        },
        {
            "uri": "sftp://fileserver/share/readme.md",
            "title": "readme.md",
            "description": "fileserver",
            "icon": "text-x-generic",
        },
    ]
    by_folder = match_recents("documents", rows)
    assert [row["title"] for row in by_folder] == ["quarterly-report.txt"]
    by_words = match_recents("quarterly documents", rows)
    assert [row["title"] for row in by_words] == ["quarterly-report.txt"]
    by_host = match_recents("fileserver", rows)
    assert [row["title"] for row in by_host] == ["readme.md"]
    assert match_recents("", rows, limit=1) == rows[:1]


def test_parse_recent_xbel_regex_unescapes_and_skips_web() -> None:
    text = """
<xbel>
  <bookmark href="https://example.com/ignore"/>
  <bookmark href="javascript:alert(1)"/>
  <bookmark href="file:javascript:alert(1)"/>
  <bookmark href="file:///tmp/a&amp;b.txt"/>
  <bookmark href='file:///tmp/single.txt'/>
  <bookmark href = "file:///tmp/spaced.txt"/>
  <bookmark href="sftp://nas.local/share/notes.txt"/>
</xbel>
"""
    uris = parse_recent_xbel(text)
    assert "file:///tmp/a&b.txt" in uris
    assert "file:///tmp/single.txt" in uris
    assert "file:///tmp/spaced.txt" in uris
    assert "sftp://nas.local/share/notes.txt" in uris
    assert parse_recent_xbel('<bookmark href="ftp://nas/a.txt"/>') == ["ftp://nas/a.txt"]
    assert parse_recent_xbel('<bookmark href="davs://nas/a.txt"/>') == ["davs://nas/a.txt"]
    assert all("example.com" not in uri and "javascript" not in uri for uri in uris)


def test_basename_from_uri_keeps_latin1_percent_bytes() -> None:
    assert basename_from_uri("file:///home/user/My%20File.pdf") == "My File.pdf"
    assert basename_from_uri("file:///tmp/a%") == "a%"
    assert basename_from_uri("file:///tmp/caf%E9.txt") == "caf%E9.txt"


def test_icon_for_basename_and_exists_budget() -> None:
    assert icon_for_basename("notes.pdf") == "x-office-document-symbolic"
    assert icon_for_basename("shot.png") == "image-x-generic-symbolic"
    assert icon_for_basename("song.mp3") == "audio-x-generic-symbolic"
    assert icon_for_basename("README") == "document-open-recent-symbolic"
    assert icon_for_basename(".bashrc") == "document-open-recent-symbolic"
    assert recent_exists_should_settle(0, 10, 800) is True
    assert recent_exists_should_settle(2, 100, 800) is False
    assert recent_exists_should_settle(2, 800, 800) is True


def test_goshos_recent_file_match_needles() -> None:
    from ulauncher.modes.launcher.recents import recent_file_matches

    assert recent_file_matches("notes.txt", "~/Documents", "docu")
    assert recent_file_matches("notes.txt", "~/Documents", "notes")
    assert recent_file_matches("notes.txt", "~/Documents", "notes documents")
    assert not recent_file_matches("notes.txt", "~/Documents", "chrome")
    assert not recent_file_matches("notes.txt", "~/Documents", "o")
    assert not recent_file_matches("notes.txt", "/home/u", "ome")


def test_search_recents_empty_until_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    notes = tmp_path / "unique-goshos-recent-xyz.txt"
    notes.write_text("ok", encoding="utf-8")
    xbel = tmp_path / "recently-used.xbel"
    xbel.write_text(
        f"""<?xml version="1.0"?>
<xbel>
  <bookmark href="{notes.as_uri()}"/>
</xbel>
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("ulauncher.modes.launcher.recents.XBEL", xbel)
    invalidate_recent_files()
    assert search_recents("unique-goshos-recent-xyz") == []
    ensure_recent_files(lambda: None)
    flush_recents_lookup()
    rows = search_recents("unique-goshos-recent-xyz")
    assert rows
    assert rows[0]["title"] == "unique-goshos-recent-xyz.txt"
