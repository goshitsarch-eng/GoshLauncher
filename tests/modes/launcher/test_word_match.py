from __future__ import annotations

from ulauncher.modes.launcher.word_match import (
    SUBSTRING_MIN,
    id_matches_query,
    keyword_matches_query,
    label_matches_query,
    path_matches_query,
    text_matches_query,
    word_prefix_match,
)


def test_word_prefix_after_delimiter() -> None:
    assert word_prefix_match("firefox browser", "browser")
    assert word_prefix_match("google chrome", "chro")
    assert not word_prefix_match("google chrome", "ogle")
    assert word_prefix_match("gnome-builder", "bui")
    assert word_prefix_match("foo bar", "bar")
    assert word_prefix_match("notes.txt", "txt")
    assert word_prefix_match("~/documents", "doc")
    assert not word_prefix_match("/home/u", "ome")
    assert not word_prefix_match("unlock", "lock")
    # first token is startswith, not wordPrefixMatch
    assert not word_prefix_match("chrome", "chro")
    assert not word_prefix_match("org.mozilla.firefox", "org")


def test_text_matches_prefix_and_substring() -> None:
    assert text_matches_query("Firefox", "fir")
    assert text_matches_query("Firefox", "fox")
    assert text_matches_query("Workspace 2", "2")
    assert not text_matches_query("Workspace 1", "o")
    assert not text_matches_query("Firefox", "zzz")


def test_id_and_label_keep_org_and_ows_out() -> None:
    assert SUBSTRING_MIN == 3
    assert id_matches_query("org.mozilla.firefox", "mozilla")
    assert id_matches_query("org.mozilla.firefox", "fire")
    assert not id_matches_query("org.mozilla.firefox", "org")
    assert not id_matches_query("org.mozilla.firefox", "zil")
    assert id_matches_query("Firefox Navigator org.mozilla.firefox", "nav")
    assert not id_matches_query("Firefox Navigator org.mozilla.firefox", "org")
    assert not id_matches_query("org.mozilla.firefox", "f")
    assert label_matches_query("Web Browser", "bro")
    assert not label_matches_query("Web Browser", "ows")
    assert label_matches_query("Write notes and lists", "write")
    assert not label_matches_query("Write notes and lists", "ite")
    assert path_matches_query("~/Documents", "doc")
    assert not path_matches_query("/home/u", "ome")
    assert keyword_matches_query("browser", "bro")
    assert not keyword_matches_query("browser", "row")
    assert keyword_matches_query("hotspot", "hot")
    assert not keyword_matches_query("hotspot", "pot")
