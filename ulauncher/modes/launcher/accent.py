"""Session accent for gnome and light looks, ported from spotlight-goshos accentColor.js."""

from __future__ import annotations

from typing import Any

ACCENT_NICKS = (
    "blue",
    "teal",
    "green",
    "yellow",
    "orange",
    "red",
    "pink",
    "purple",
    "slate",
)
ACCENT_HEX = {
    "blue": "#3584e4",
    "teal": "#2190a4",
    "green": "#3a944a",
    "yellow": "#c88800",
    "orange": "#ed5b00",
    "red": "#e62d42",
    "pink": "#d56199",
    "purple": "#9141ac",
    "slate": "#6f8396",
}
_ACCENT_LOOKS = frozenset({"gnome", "light"})


def accent_nick_from_enum(value: int) -> str:
    if not isinstance(value, int) or value < 0 or value >= len(ACCENT_NICKS):
        return "blue"
    return ACCENT_NICKS[value]


def accent_nick_from_settings(has_key: bool, enum_value: int) -> str:
    if not has_key:
        return "blue"
    return accent_nick_from_enum(enum_value)


def accent_hex(nick: str) -> str:
    return ACCENT_HEX.get(nick, ACCENT_HEX["blue"])


def accent_style_class(theme_id: str, nick: str) -> str:
    if theme_id not in _ACCENT_LOOKS:
        return ""
    if not nick or nick == "blue":
        return ""
    return f"gosh-accent-{nick}"


def schema_has_accent_key(schema: Any) -> bool:
    has_key = getattr(schema, "has_key", None)
    if schema is None or not callable(has_key):
        return False
    return bool(has_key("accent-color"))


def next_accent_listen_action(schema: Any) -> str:
    if not schema_has_accent_key(schema):
        return "skip"
    return "listen"


def session_accent_nick() -> str:
    """The GNOME session accent color nick, via the gsettings CLI (absent on
    non-GNOME sessions, where Kirigami follows the palette accent natively)."""
    import subprocess

    try:
        raw = (
            subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .strip()
            .strip("'\"")
        )
    except (OSError, subprocess.SubprocessError):
        return "blue"
    return raw if raw in ACCENT_NICKS else "blue"
