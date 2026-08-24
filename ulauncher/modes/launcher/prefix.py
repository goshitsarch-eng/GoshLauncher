"""Leading-character prefixes that force a single provider."""

from __future__ import annotations

from typing import TypedDict

PREFIXES = {
    "=": "calculator",
    "@": "web",
    "#": "settings",
    "$": "windows",
    ".": "files",
    "!": "command",
}

_SPACE_PREFIXES = {".", "$", "#"}


class ParsedQuery(TypedDict):
    mode: str
    query: str


def is_prefix_token(trimmed: str, prefix: str) -> bool:
    if not trimmed or trimmed[0] != prefix:
        return False
    if prefix not in _SPACE_PREFIXES:
        return True
    return len(trimmed) == 1 or trimmed[1] == " "


def parse_query(text: str) -> ParsedQuery:
    trimmed = text.strip()
    if not trimmed:
        return {"mode": "all", "query": ""}
    prefix = trimmed[0]
    mode = PREFIXES.get(prefix)
    if not mode or not is_prefix_token(trimmed, prefix):
        return {"mode": "all", "query": trimmed}
    return {"mode": mode, "query": trimmed[1:].strip()}
