"""Goshos ``searchEntry.js``: look hint placeholder, 20px symbolic search icon."""

from __future__ import annotations

from typing import Any, TypedDict

from ulauncher.modes.launcher.looks import get_look, search_icon_style_class

SEARCH_ICON_NAME = "system-search-symbolic"
SEARCH_ICON_PX = 20


class SearchEntrySpec(TypedDict):
    placeholder: str
    icon_name: str
    icon_px: int
    icon_visible: bool
    icon_style_class: str


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)


def search_entry_spec(settings: Any) -> SearchEntrySpec:
    """Placeholder = look ``hint``; icon visibility follows ``show_search_icon``."""
    look = get_look(str(_setting(settings, "look_id", "spotlight") or "spotlight"))
    icon_visible = bool(_setting(settings, "show_search_icon", True))
    return {
        "placeholder": look["hint"],
        "icon_name": SEARCH_ICON_NAME,
        "icon_px": SEARCH_ICON_PX,
        "icon_visible": icon_visible,
        "icon_style_class": search_icon_style_class(icon_visible),
    }
