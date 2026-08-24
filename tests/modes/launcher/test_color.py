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


def _hex(query: str) -> str | None:
    hit = parse_color(query)
    return None if hit is None else str(hit["hex"])


def test_goshos_hex_forms() -> None:
    assert _hex("#AABBCC") == "#aabbcc"
    assert _hex("#f00f") == "#ff0000"
    assert _hex("#ff000080") == "#ff0000"


def test_goshos_modern_css_functions() -> None:
    assert _hex("rgb(255 0 0)") == "#ff0000"
    assert _hex("rgb(255 0 0 / 40%)") == "#ff0000"
    assert _hex("rgba(0,128,255,0.5)") == "#0080ff"
    assert _hex("rgb(256, 0, 0)") is None
    assert _hex("rgb(100%, 0%, 0%)") == "#ff0000"
    assert _hex("rgb(100% 0% 0%)") == "#ff0000"
    assert _hex("rgb(100 %, 0 %, 0 %)") == "#ff0000"
    assert _hex("rgb(101%, 0%, 0%)") is None
    assert _hex("rgb 255, 0, 0") == "#ff0000"
    assert _hex("rgb 100% 0% 0%") == "#ff0000"
    assert _hex("rgba 255 0 0 0.5") == "#ff0000"
    assert _hex("rgb") is None
    assert _hex("hsl(0 100% 50%)") == "#ff0000"
    assert _hex("hsl(0deg 100% 50%)") == "#ff0000"
    assert _hex("hsl(0deg, 100%, 50%)") == "#ff0000"
    assert _hex("hsl(0 100% 50% / 0.4)") == "#ff0000"
    assert _hex("hsl(0 100 50)") == "#ff0000"
    assert _hex("hsl 0 100% 50%") == "#ff0000"
    assert _hex("hsl 0, 100%, 50%") == "#ff0000"
    assert _hex("hsla(120, 100%, 50%, 0.4)") == "#00ff00"
    assert _hex("hsl(0, 200%, 50%)") is None
    assert _hex("hwb(0 0% 0%)") == "#ff0000"
    assert _hex("hwb(0deg, 0%, 0%)") == "#ff0000"
    assert _hex("hwb(0deg 0% 0%)") == "#ff0000"
    assert _hex("hwb(120 0% 0%)") == "#00ff00"
    assert _hex("hwb(0 100% 0%)") == "#ffffff"
    assert _hex("hwb(0 0% 100%)") == "#000000"
    assert _hex("hwb(0 50% 50%)") == "#808080"
    assert _hex("hwb(0 20% 20%)") == "#cc3333"
    assert _hex("hwb(0 0% 0% / 0.4)") == "#ff0000"
    assert _hex("hwba(240, 0%, 0%, 0.4)") == "#0000ff"
    assert _hex("hwb(0 200% 0%)") is None
    assert _hex("hwb 0 0% 0%") == "#ff0000"
    assert _hex("hwb 0, 0%, 0%") == "#ff0000"
