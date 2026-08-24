"""GTK clips CSS box-shadow at the window edge; goshos paints it on the stage."""

from __future__ import annotations

import re

# goshos uses `0 <offset-y>px <blur>px rgba(...)`. `none` does not match.
_BOX_SHADOW_BLUR = re.compile(r"box-shadow:\s*0\s+\d+px\s+(\d+)px")


def css_box_shadow_blurs(css: str) -> list[int]:
    return [int(match.group(1)) for match in _BOX_SHADOW_BLUR.finditer(css)]


def default_stylesheet_section(css: str) -> str:
    start = css.find(".gosh-theme-")
    if start < 0:
        return css
    return css[:start]


def look_stylesheet_section(css: str, look_id: str) -> str:
    marker = f".gosh-theme-{look_id}"
    start = css.find(marker)
    if start < 0:
        return ""
    rest = css[start:]
    nxt = re.search(r"\n\.gosh-theme-(?!" + re.escape(look_id) + r"(?:\.|\s|\{))", rest)
    return rest[: nxt.start()] if nxt else rest


def look_shadow_inset(css: str, look_id: str) -> int:
    """Padding GTK needs so the look's CSS blur is not clipped."""
    blurs = css_box_shadow_blurs(default_stylesheet_section(css) + look_stylesheet_section(css, look_id))
    return max(blurs) if blurs else 0


def origin_minus_inset(pos: float, inset: float) -> int:
    """Shift the window so the card, not the shadow padding, sits on the goshos origin."""
    return int(pos) - int(inset)


def surface_size_with_inset(size: float, inset: float) -> int:
    return int(size) + 2 * int(inset)
