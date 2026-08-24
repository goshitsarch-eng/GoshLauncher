"""Map a key press to a popup action, ported from spotlight-goshos keyAction.js."""

from __future__ import annotations

from typing import Any


def normalize_key_name(key: str) -> str:
    aliases = {
        "KP_Down": "Down",
        "KP_Up": "Up",
        "KP_Page_Down": "Page_Down",
        "KP_Page_Up": "Page_Up",
        "KP_Home": "Home",
        "KP_End": "End",
        "KP_Enter": "KP_Enter",
        "KP_Return": "Return",
    }
    if key.startswith("KP_") and len(key) == 4 and key[3].isdigit():
        return key[3]
    return aliases.get(key, key)


def resolve_key_action(key: str, shift: bool, alt: bool, show_numbers: bool) -> dict[str, Any]:
    key = normalize_key_name(key)
    if show_numbers and alt and key.isdigit():
        digit = int(key)
        if 1 <= digit <= 9:
            return {"type": "activate-index", "index": digit - 1}

    if key == "Escape":
        return {"type": "close"}
    if key == "Down":
        return {"type": "move", "delta": 1}
    if key == "Tab":
        return {"type": "move", "delta": -1 if shift else 1}
    if key in {"Up", "ISO_Left_Tab"}:
        return {"type": "move", "delta": -1}
    if key == "Page_Down":
        return {"type": "move", "delta": 5}
    if key == "Page_Up":
        return {"type": "move", "delta": -5}
    if key in {"Return", "KP_Enter"}:
        return {"type": "activate"}
    return {"type": "propagate"}


def resolve_ctrl_nav(key: str) -> dict[str, Any] | None:
    name = normalize_key_name(key).lower()
    if name in {"j", "n"}:
        return {"type": "move", "delta": 1}
    if name in {"k", "p"}:
        return {"type": "move", "delta": -1}
    return None


def cursor_at_start(cursor: int) -> bool:
    return cursor == 0


def cursor_at_end(cursor: int, text_length: int) -> bool:
    return text_length == 0 or cursor < 0 or cursor >= text_length


def resolve_home_end_action(key: str, cursor: int, text_length: int) -> dict[str, Any] | None:
    key = normalize_key_name(key)
    if key == "Home":
        if cursor_at_start(cursor):
            return {"type": "move", "delta": -999}
        return {"type": "propagate"}
    if key == "End":
        if cursor_at_end(cursor, text_length):
            return {"type": "move", "delta": 999}
        return {"type": "propagate"}
    return None
