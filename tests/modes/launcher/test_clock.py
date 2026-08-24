from __future__ import annotations

from ulauncher.modes.launcher.clock import format_date_title, match_clock, time_query_kind


def test_time_phrases() -> None:
    for query in (
        "time",
        "now",
        "what time is it",
        "what's the time",
        "current time",
        "what's the time right now",
        "show me the time",
        "tell me the time",
        "tell me what time it is",
    ):
        assert time_query_kind(query) == "time"
        hit = match_clock(query)
        assert hit is not None
        assert "time" in hit


def test_date_phrases() -> None:
    for query in ("date", "today", "what day is it", "what's the date"):
        assert time_query_kind(query) == "date"
    assert time_query_kind("today's date") == "date"
    assert time_query_kind("tell me the day") == "date"


def test_relative_days() -> None:
    assert time_query_kind("tomorrow") == "tomorrow"
    assert time_query_kind("yesterday") == "yesterday"
    assert match_clock("firefox") is None


def test_date_title_format() -> None:
    assert format_date_title("Monday", 5, "January", 2026) == "Monday, 5 January 2026"
    hit = match_clock("date")
    assert hit is not None
    assert hit["title"].startswith(f"{hit['weekday']}, ")
    assert hit["copy_text"] == hit["title"]
    assert hit["description"] == hit["date"]
