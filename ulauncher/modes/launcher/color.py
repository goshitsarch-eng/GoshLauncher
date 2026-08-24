from __future__ import annotations

import colorsys
import re
from typing import Optional

from ulauncher.modes.launcher.prefix import PREFIXES

CSS_NAMED_COLORS: dict[str, str] = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "grey": "#808080",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}

_HEX_RE = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$", re.IGNORECASE)
# goshos colorMatch.js: comma, space-separated, optional deg, optional slash alpha
_RGB_RES = (
    re.compile(
        r"^rgba?\(\s*([\d.]+)\s*%\s*,\s*([\d.]+)\s*%\s*,\s*([\d.]+)\s*%\s*(?:,\s*[\d.]+\s*)?\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\(\s*([\d.]+)\s*%\s+([\d.]+)\s*%\s+([\d.]+)\s*%(?:\s*/\s*[\d.%]+)?\s*\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\s+([\d.]+)\s*%\s*,\s*([\d.]+)\s*%\s*,\s*([\d.]+)\s*%(?:\s*,\s*[\d.]+)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\s+([\d.]+)\s*%\s+([\d.]+)\s*%\s+([\d.]+)\s*%(?:\s+[\d.%]+)?\s*$",
        re.IGNORECASE,
    ),
)
_RGB_BYTE_RES = (
    re.compile(
        r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\(\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})(?:\s*/\s*[\d.%]+)?\s*\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\s+(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^rgba?\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})(?:\s+[\d.]+)?\s*$",
        re.IGNORECASE,
    ),
)
_HSL_RES = (
    re.compile(
        r"^hsla?\(\s*(-?[\d.]+)(?:deg)?\s*,\s*([\d.]+)\s*%?\s*,\s*([\d.]+)\s*%?\s*(?:,\s*[\d.]+\s*)?\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hsla?\(\s*(-?[\d.]+)(?:deg)?\s+([\d.]+)\s*%?\s+([\d.]+)\s*%?(?:\s*/\s*[\d.%]+)?\s*\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hsla?\s+(-?[\d.]+)(?:deg)?\s*,\s*([\d.]+)\s*%?\s*,\s*([\d.]+)\s*%?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hsla?\s+(-?[\d.]+)(?:deg)?\s+([\d.]+)\s*%?\s+([\d.]+)\s*%?\s*$",
        re.IGNORECASE,
    ),
)
_HWB_RES = (
    re.compile(
        r"^hwba?\(\s*(-?[\d.]+)(?:deg)?\s*,\s*([\d.]+)\s*%?\s*,\s*([\d.]+)\s*%?\s*(?:,\s*[\d.]+\s*)?\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hwba?\(\s*(-?[\d.]+)(?:deg)?\s+([\d.]+)\s*%?\s+([\d.]+)\s*%?(?:\s*/\s*[\d.%]+)?\s*\)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hwba?\s+(-?[\d.]+)(?:deg)?\s*,\s*([\d.]+)\s*%?\s*,\s*([\d.]+)\s*%?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^hwba?\s+(-?[\d.]+)(?:deg)?\s+([\d.]+)\s*%?\s+([\d.]+)\s*%?\s*$",
        re.IGNORECASE,
    ),
)


def _first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> re.Match[str] | None:
    for pattern in patterns:
        match = pattern.match(text)
        if match:
            return match
    return None


def _byte_hex(n: int) -> str:
    return f"{max(0, min(255, n)):02x}"


def _rgb_bytes_to_hex(r: float, g: float, b: float) -> str:
    return f"#{_byte_hex(round(r * 255))}{_byte_hex(round(g * 255))}{_byte_hex(round(b * 255))}"


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    rf, gf, bf = colorsys.hls_to_rgb(((h % 360) + 360) % 360 / 360.0, l / 100.0, s / 100.0)
    return _rgb_bytes_to_hex(rf, gf, bf)


def _hwb_to_hex(h: float, w: float, bl: float) -> str:
    white = w / 100.0
    black = bl / 100.0
    if white + black >= 1:
        gray = white / (white + black)
        return _rgb_bytes_to_hex(gray, gray, gray)
    rf, gf, bf = colorsys.hls_to_rgb(((h % 360) + 360) % 360 / 360.0, 0.5, 1.0)
    factor = 1 - white - black
    return _rgb_bytes_to_hex(rf * factor + white, gf * factor + white, bf * factor + white)


def _parse_rgb_hex(text: str) -> str | None:
    percent = _first_match(text, _RGB_RES)
    if percent:
        r, g, b = float(percent.group(1)), float(percent.group(2)), float(percent.group(3))
        if r > 100 or g > 100 or b > 100:
            return None
        return f"#{_byte_hex(round(r * 255 / 100))}{_byte_hex(round(g * 255 / 100))}{_byte_hex(round(b * 255 / 100))}"
    match = _first_match(text, _RGB_BYTE_RES)
    if not match:
        return None
    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if r > 255 or g > 255 or b > 255:
        return None
    return f"#{_byte_hex(r)}{_byte_hex(g)}{_byte_hex(b)}"


def _parse_hsl_hex(text: str) -> str | None:
    match = _first_match(text, _HSL_RES)
    if not match:
        return None
    s, l = float(match.group(2)), float(match.group(3))
    if s > 100 or l > 100:
        return None
    return _hsl_to_hex(float(match.group(1)), s, l)


def _parse_hwb_hex(text: str) -> str | None:
    match = _first_match(text, _HWB_RES)
    if not match:
        return None
    w, b = float(match.group(2)), float(match.group(3))
    if w > 100 or b > 100:
        return None
    return _hwb_to_hex(float(match.group(1)), w, b)


def expand_hex(hex_s: str) -> str:
    h = hex_s.lstrip("#").lower()
    if len(h) == 3 or len(h) == 4:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        return "#" + h[:6]
    return "#" + h


def hex_to_rgb(hex_s: str) -> tuple[int, int, int]:
    h = expand_hex(hex_s)[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _color_dict(hx: str, source: str, name: str | None = None) -> dict:
    r, g, b = hex_to_rgb(hx)
    parsed: dict = {"hex": hx, "r": r, "g": g, "b": b, "source": source}
    if name is not None:
        parsed["name"] = name
    return parsed


def parse_color(query: str) -> Optional[dict]:
    """Return parsed color or None. Rejects settings-style ``# wifi``."""
    raw = query.strip()
    if not raw:
        return None
    if raw[0] in PREFIXES and not raw.startswith("#"):
        return None
    # # followed by a space is a settings prefix, not a color
    if raw.startswith("#") and len(raw) > 1 and raw[1].isspace():
        return None

    lower = raw.lower()
    named = CSS_NAMED_COLORS.get(lower)
    if named:
        return _color_dict(named, "name", name=lower)

    # goshos requires a leading hash so cafe, dead, and ff0000 stay app searches
    hex_m = _HEX_RE.match(raw) if raw.startswith("#") else None
    if hex_m:
        return _color_dict(expand_hex("#" + hex_m.group(1)), "hex")

    # CSS Color 4 function syntax from goshos colorMatch.js (space, comma, slash alpha).
    rgb_hex = _parse_rgb_hex(raw)
    if rgb_hex is not None:
        return _color_dict(rgb_hex, "rgb")
    hsl_hex = _parse_hsl_hex(raw)
    if hsl_hex is not None:
        return _color_dict(hsl_hex, "hsl")
    hwb_hex = _parse_hwb_hex(raw)
    if hwb_hex is not None:
        return _color_dict(hwb_hex, "hwb")
    return None


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return int(round(h * 360)) % 360, int(round(s * 100)), int(round(l * 100))
