"""Local clock and calendar queries, ported from spotlight-goshos timeMatch.js."""

from __future__ import annotations

import re
from typing import Optional

_TRAILING_NOW = re.compile(r"(?:\s+(?:right\s+now|currently|at\s+the\s+moment|please))+$")
_LEADING_VERB = re.compile(r"^(?:what(?:['’]?s| is)|show(?:\s+me)?|tell\s+me(?:\s+what)?|give\s+me)\s+")
_TRAILING_IS_IT = re.compile(r"\s+(?:is\s+it|it\s+is)$")


def normalize_time_query(query: str) -> str:
    q = query.strip().lower().replace("'", "").replace("’", "")
    q = re.sub(r"[?!.,]+$", "", q)
    q = _TRAILING_NOW.sub("", q).strip()
    q = _LEADING_VERB.sub("", q).strip()
    q = _TRAILING_IS_IT.sub("", q).strip()
    q = re.sub(r"^(?:the|a|an|my|current|local|todays?)\s+", "", q).strip()
    q = re.sub(r"\s+now$", "", q).strip()
    return q


def time_query_kind(query: str) -> str | None:
    q = normalize_time_query(query)
    if q in {
        "time",
        "now",
        "clock",
        "what time",
        "current time",
        "whats the time",
        "what is the time",
        "what time is it",
        "what time it is",
        "what the time is",
        "the time",
    }:
        return "time"
    if q in {
        "date",
        "today",
        "calendar",
        "what date",
        "what day",
        "what date is it",
        "current date",
        "whats the date",
        "what is the date",
        "todays date",
        "date today",
        "todays",
        "what day is it",
        "what day is it today",
        "whats the day",
        "what day it is",
        "what the date is",
        "day",
        "current day",
        "day today",
        "weekday",
        "current weekday",
        "day of week",
        "day of the week",
        "the date",
        "the day",
    }:
        return "date"
    if q == "tomorrow":
        return "tomorrow"
    if q == "yesterday":
        return "yesterday"
    return None


def format_clock(hours: int, minutes: int, seconds: int) -> str:
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_date_title(weekday: str, day: int, month: str, year: int) -> str:
    return f"{weekday}, {day} {month} {year}"


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def weekday_name(day_of_week: int) -> str:
    if day_of_week < 1 or day_of_week > 7:
        return ""
    return WEEKDAYS[day_of_week - 1]


def month_name(month: int) -> str:
    if month < 1 or month > 12:
        return ""
    return MONTHS[month - 1]


def format_iso_date(year: int, month: int, day: int) -> str:
    return f"{year}-{month:02d}-{day:02d}"


def date_offset_days(kind: str) -> int:
    if kind == "tomorrow":
        return 1
    if kind == "yesterday":
        return -1
    return 0


def match_clock(query: str) -> Optional[dict]:
    kind = time_query_kind(query)
    if not kind:
        return None
    return _payload(kind)


def _payload(kind: str) -> dict:
    from ulauncher.gi import GLib

    now = GLib.DateTime.new_now_local()
    when = now.add_days(date_offset_days(kind)) or now
    weekday = weekday_name(when.get_day_of_week())
    iso_date = format_iso_date(when.get_year(), when.get_month(), when.get_day_of_month())
    clock = format_clock(when.get_hour(), when.get_minute(), when.get_second())
    date_title = format_date_title(weekday, when.get_day_of_month(), month_name(when.get_month()), when.get_year())
    iso = when.format("%Y-%m-%dT%H:%M:%S") or iso_date
    if kind == "time":
        title = clock
        description = weekday
        copy_text = clock
    else:
        title = date_title
        description = iso_date
        copy_text = date_title
    return {
        "kind": kind,
        "time": clock,
        "date": iso_date,
        "weekday": weekday,
        "iso": iso,
        "title": title,
        "description": description,
        "copy_text": copy_text,
    }
