"""Spoken cardinals used by math and units, ported from spotlight-goshos numberWords.js."""

from __future__ import annotations

import re

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
}

TENS_WORDS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

ORDINAL_WORDS = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
    "eleventh": "11",
    "twelfth": "12",
}

_NUMBER_WORD_RE = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b",
    re.IGNORECASE,
)
_ORDINAL_POWER_RE = re.compile(
    r"\bto the\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
    r"tenth|eleventh|twelfth)(?:\s+power)?\b",
    re.IGNORECASE,
)
_TENS_THOUSAND_RE = re.compile(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\s+thousand\b", re.IGNORECASE)
_ONES_THOUSAND_RE = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\s+thousand\b",
    re.IGNORECASE,
)
_ONES_HUNDRED_RE = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\s+hundred\b",
    re.IGNORECASE,
)
_TENS_ONES_RE = re.compile(
    r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-](one|two|three|four|five|six|seven|eight|nine))?\b",
    re.IGNORECASE,
)


def replace_number_words(text: str) -> str:
    out = re.sub(r"\ba\s+billion\b", "1000000000", text, flags=re.IGNORECASE)
    out = re.sub(r"\ba\s+million\b", "1000000", out, flags=re.IGNORECASE)
    out = re.sub(r"\ba\s+thousand\b", "1000", out, flags=re.IGNORECASE)
    out = re.sub(r"\ba\s+hundred\b", "100", out, flags=re.IGNORECASE)
    out = _TENS_THOUSAND_RE.sub(lambda m: str(TENS_WORDS[m.group(1).lower()] * 1000), out)
    out = _ONES_THOUSAND_RE.sub(lambda m: str(int(NUMBER_WORDS[m.group(1).lower()]) * 1000), out)
    out = _ONES_HUNDRED_RE.sub(lambda m: str(int(NUMBER_WORDS[m.group(1).lower()]) * 100), out)

    def tens_ones(match: re.Match[str]) -> str:
        n = TENS_WORDS[match.group(1).lower()]
        if match.group(2):
            n += int(NUMBER_WORDS[match.group(2).lower()])
        return str(n)

    out = _TENS_ONES_RE.sub(tens_ones, out)
    out = re.sub(r"\bthousand\b", "1000", out, flags=re.IGNORECASE)
    out = re.sub(r"\bhundred\b", "100", out, flags=re.IGNORECASE)
    out = _NUMBER_WORD_RE.sub(lambda m: NUMBER_WORDS[m.group(0).lower()], out)
    out = re.sub(r"\b(\d+)\s+billion\b", lambda m: str(int(m.group(1)) * 1_000_000_000), out, flags=re.IGNORECASE)
    out = re.sub(r"\b(\d+)\s+million\b", lambda m: str(int(m.group(1)) * 1_000_000), out, flags=re.IGNORECASE)
    out = re.sub(
        r"\b(\d+000)\s+(?:and\s+)?(\d{1,3})\b",
        lambda m: str(int(m.group(1)) + int(m.group(2))),
        out,
    )
    out = re.sub(
        r"\b(\d+00)\s+(?:and\s+)?(\d{1,2})\b",
        lambda m: str(int(m.group(1)) + int(m.group(2))),
        out,
    )
    return re.sub(
        r"\b(\d{7,})\s+(?:and\s+)?(\d{1,3})\b",
        lambda m: str(int(m.group(1)) + int(m.group(2))),
        out,
    )


def replace_ordinal_power(text: str) -> str:
    return _ORDINAL_POWER_RE.sub(lambda m: f"^{ORDINAL_WORDS[m.group(1).lower()]}", text)
