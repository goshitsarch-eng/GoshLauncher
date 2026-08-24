from __future__ import annotations

from ulauncher.modes.launcher.clock import match_clock, time_query_kind


def test_time_phrases() -> None:
    for query in ("time", "now", "what time is it", "what's the time", "current time"):
        assert time_query_kind(query) == "time"
        hit = match_clock(query)
        assert hit is not None
        assert "time" in hit


def test_date_phrases() -> None:
    for query in ("date", "today", "what day is it", "what's the date"):
        assert time_query_kind(query) == "date"


def test_relative_days() -> None:
    assert time_query_kind("tomorrow") == "tomorrow"
    assert time_query_kind("yesterday") == "yesterday"
    assert match_clock("firefox") is None
