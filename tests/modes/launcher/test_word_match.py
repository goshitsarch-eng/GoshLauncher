from __future__ import annotations

from ulauncher.modes.launcher.word_match import text_matches_query, word_prefix_match


def test_word_prefix_after_delimiter() -> None:
    assert word_prefix_match("firefox browser", "browser")
    assert word_prefix_match("org.mozilla.firefox", "mozilla")
    assert not word_prefix_match("unlock", "lock")


def test_text_matches_prefix_and_substring() -> None:
    assert text_matches_query("Firefox", "fir")
    assert text_matches_query("Firefox", "fox")
    assert not text_matches_query("Firefox", "zzz")
