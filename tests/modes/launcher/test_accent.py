from __future__ import annotations

from ulauncher.modes.launcher.accent import (
    accent_hex,
    accent_nick_from_enum,
    accent_nick_from_settings,
    accent_style_class,
    next_accent_listen_action,
    schema_has_accent_key,
)


class _Schema:
    def __init__(self, has_accent: bool) -> None:
        self._has_accent = has_accent

    def has_key(self, name: str) -> bool:
        return self._has_accent and name == "accent-color"


def test_accent_nick_and_style_class() -> None:
    assert accent_nick_from_enum(0) == "blue"
    assert accent_nick_from_enum(1) == "teal"
    assert accent_nick_from_enum(-1) == "blue"
    assert accent_nick_from_settings(False, 3) == "blue"
    assert accent_nick_from_settings(True, 3) == "yellow"
    assert accent_hex("teal") == "#2190a4"
    assert accent_style_class("gnome", "blue") == ""
    assert accent_style_class("gnome", "teal") == "gosh-accent-teal"
    assert accent_style_class("spotlight", "teal") == ""
    assert accent_style_class("light", "pink") == "gosh-accent-pink"


def test_accent_schema_listen_action() -> None:
    assert schema_has_accent_key(None) is False
    assert schema_has_accent_key(_Schema(False)) is False
    assert schema_has_accent_key(_Schema(True)) is True
    assert next_accent_listen_action(_Schema(False)) == "skip"
    assert next_accent_listen_action(_Schema(True)) == "listen"
