from __future__ import annotations

from pathlib import Path

from ulauncher.modes.launcher.clock import (
    date_offset_days,
    format_date_title,
    format_iso_date,
    match_clock,
    month_name,
    normalize_time_query,
    time_query_kind,
    weekday_name,
)


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
        "what time is it now",
        "clock",
        "what time is it right now",
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
    assert time_query_kind("what's the day") == "date"
    assert time_query_kind("tell me the day please") == "date"


def test_relative_days() -> None:
    assert time_query_kind("tomorrow") == "tomorrow"
    assert time_query_kind("yesterday") == "yesterday"
    assert match_clock("firefox") is None


def test_date_title_format() -> None:
    assert format_date_title("Monday", 5, "January", 2026) == "Monday, 5 January 2026"
    assert weekday_name(1) == "Monday"
    assert weekday_name(7) == "Sunday"
    assert weekday_name(0) == ""
    assert month_name(8) == "August"
    assert month_name(13) == ""
    assert format_iso_date(2026, 8, 3) == "2026-08-03"
    assert date_offset_days("tomorrow") == 1
    assert date_offset_days("yesterday") == -1
    assert date_offset_days("time") == 0
    hit = match_clock("date")
    assert hit is not None
    assert hit["title"].startswith(f"{hit['weekday']}, ")
    assert hit["weekday"] in {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }
    assert hit["copy_text"] == hit["title"]
    assert hit["description"] == hit["date"]
    source = Path(__file__).resolve().parents[3] / "ulauncher" / "modes" / "launcher" / "clock.py"
    text = source.read_text()
    assert "datetime.now()" in text
    assert "GLib" not in text


def test_goshos_clock_false_positives() -> None:
    assert time_query_kind("days") is None
    assert time_query_kind("daylight") is None
    assert time_query_kind("timeout") is None
    assert time_query_kind("yesterdays") is None
    assert time_query_kind("day") == "date"
    assert time_query_kind("weekday") == "date"
    assert time_query_kind("day of the week") == "date"
    assert time_query_kind("current date") == "date"
    assert time_query_kind("what the time is") == "time"
    assert time_query_kind("what's the current day") == "date"
    assert time_query_kind("tell me the day please") == "date"
    assert normalize_time_query("time right now") == "time"
    assert normalize_time_query("now") == "now"
