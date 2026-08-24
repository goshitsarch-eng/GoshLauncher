"""Hold compositor unredirect while the popup is open.

Ported from Spotlight-goshos unredirect.js. A GTK app has no mutter unredirect
API; callers still follow hold/release so a future compositor backend can plug in.
"""

from __future__ import annotations


def unredirect_api(has_compositor_method: bool, has_display_method: bool) -> str:
    if has_compositor_method:
        return "compositor"
    if has_display_method:
        return "display"
    return ""


def next_unredirect_action(held: bool, want_held: bool, api: str) -> str:
    if not api:
        return "keep"
    if want_held and not held:
        return "hold"
    if not want_held and held:
        return "release"
    return "keep"
