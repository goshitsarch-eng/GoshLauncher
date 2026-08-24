from __future__ import annotations

from pathlib import Path

from ulauncher.modes.launcher.recents import match_recents, parse_xbel, usable_recent_uri


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
