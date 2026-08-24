from __future__ import annotations

import colorsys
import math
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
_FUNC_RE = re.compile(
    r"^(rgba?|hsla?|hwb)\s*\(\s*([^)]+)\s*\)$",
    re.IGNORECASE,
)


def _clamp(n: float, lo: float = 0, hi: float = 1) -> float:
    return max(lo, min(hi, n))


def _parse_channel(raw: str, *, percent: bool | None = None, max_value: float = 255) -> Optional[float]:
    s = raw.strip()
    if not s:
        return None
    is_pct = s.endswith("%")
    if is_pct:
        s = s[:-1].strip()
    try:
        value = float(s)
    except ValueError:
        return None
    if is_pct or percent is True:
        return _clamp(value / 100.0)
    if percent is False:
        return _clamp(value / max_value)
    return _clamp(value / max_value)


def _parse_hue(raw: str) -> Optional[float]:
    s = raw.strip().lower()
    if not s:
        return None
    mul = 1.0
    if s.endswith("turn"):
        mul = 360.0
        s = s[:-4].strip()
    elif s.endswith("rad"):
        mul = 180.0 / math.pi
        s = s[:-3].strip()
    elif s.endswith("grad"):
        mul = 0.9
        s = s[:-4].strip()
    elif s.endswith("deg"):
        s = s[:-3].strip()
    try:
        return (float(s) * mul) % 360.0
    except ValueError:
        return None


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
        r, g, b = hex_to_rgb(named)
        return {"hex": named, "r": r, "g": g, "b": b, "source": "name", "name": lower}

    # goshos requires a leading hash so cafe, dead, and ff0000 stay app searches
    hex_m = _HEX_RE.match(raw.replace(" ", "")) if raw.startswith("#") else None
    if hex_m:
        hx = expand_hex("#" + hex_m.group(1))
        r, g, b = hex_to_rgb(hx)
        return {"hex": hx, "r": r, "g": g, "b": b, "source": "hex"}

    func = _FUNC_RE.match(lower.replace(" ", " "))
    if not func:
        # allow "rgb 255 0 0" / "hsl 0 100% 50%"
        parts = re.split(r"[\s,]+", lower)
        if parts and parts[0] in ("rgb", "rgba", "hsl", "hsla", "hwb") and len(parts) >= 4:
            kind = parts[0]
            args = parts[1:5]
            return _from_func(kind, args)
        return None

    kind = func.group(1).lower()
    args = [a.strip() for a in re.split(r"[,/]", func.group(2)) if a.strip()]
    return _from_func(kind, args)


def _from_func(kind: str, args: list[str]) -> Optional[dict]:
    if kind in ("rgb", "rgba"):
        if len(args) < 3:
            return None
        r = _parse_channel(args[0], max_value=255)
        g = _parse_channel(args[1], max_value=255)
        b = _parse_channel(args[2], max_value=255)
        if r is None or g is None or b is None:
            return None
        ri, gi, bi = int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
        return {"hex": rgb_to_hex(ri, gi, bi), "r": ri, "g": gi, "b": bi, "source": kind}
    if kind in ("hsl", "hsla"):
        if len(args) < 3:
            return None
        h = _parse_hue(args[0])
        s = _parse_channel(args[1], percent=True)
        l = _parse_channel(args[2], percent=True)
        if h is None or s is None or l is None:
            return None
        rf, gf, bf = colorsys.hls_to_rgb(h / 360.0, l, s)
        ri, gi, bi = int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255))
        return {"hex": rgb_to_hex(ri, gi, bi), "r": ri, "g": gi, "b": bi, "source": kind}
    if kind == "hwb":
        if len(args) < 3:
            return None
        h = _parse_hue(args[0])
        w = _parse_channel(args[1], percent=True)
        bl = _parse_channel(args[2], percent=True)
        if h is None or w is None or bl is None:
            return None
        # hwb to rgb
        rf, gf, bf = colorsys.hls_to_rgb(h / 360.0, 0.5, 1.0)
        rf = rf * (1 - w - bl) + w
        gf = gf * (1 - w - bl) + w
        bf = bf * (1 - w - bl) + w
        ri, gi, bi = int(round(_clamp(rf) * 255)), int(round(_clamp(gf) * 255)), int(round(_clamp(bf) * 255))
        return {"hex": rgb_to_hex(ri, gi, bi), "r": ri, "g": gi, "b": bi, "source": "hwb"}
    return None


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return int(round(h * 360)) % 360, int(round(s * 100)), int(round(l * 100))
