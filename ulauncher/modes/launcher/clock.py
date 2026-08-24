"""Local clock and calendar queries, ported from spotlight-goshos timeMatch.js."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
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


def match_clock(query: str) -> Optional[dict]:
    kind = time_query_kind(query)
    if not kind:
        return None
    return _payload(kind)


def _payload(kind: str) -> dict:
    now = datetime.now()
    offset = 1 if kind == "tomorrow" else -1 if kind == "yesterday" else 0
    day = now + timedelta(days=offset)
    return {
        "kind": kind,
        "time": day.strftime("%H:%M:%S"),
        "date": day.strftime("%Y-%m-%d"),
        "weekday": day.strftime("%A"),
        "iso": day.isoformat(timespec="seconds"),
    }
