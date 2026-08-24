from __future__ import annotations

from ulauncher.modes.launcher.color import parse_color


def test_hash_hex_parses() -> None:
    hit = parse_color("#ff0000")
    assert hit is not None
    assert hit["hex"] == "#ff0000"
    assert hit["r"] == 255
    assert parse_color("#f00")["hex"] == "#ff0000"


def test_bare_hex_is_not_a_color() -> None:
    assert parse_color("ff0000") is None
    assert parse_color("cafe") is None
    assert parse_color("dead") is None


def test_settings_prefix_is_not_a_color() -> None:
    assert parse_color("# wifi") is None
    assert parse_color("#wifi") is None


def test_named_and_rgb() -> None:
    assert parse_color("red")["hex"] == "#ff0000"
    assert parse_color("rgb 255 0 0")["hex"] == "#ff0000"
    assert parse_color("rgb(255, 0, 0)")["hex"] == "#ff0000"
