"""Map show_preferences() arguments to Adw preference pages."""

from __future__ import annotations

# goshos prefs.js order, then desktop-app pages this GTK launcher still needs.
GOSHOS_PAGE_IDS = ("shortcut", "appearance", "features", "web-search", "about")
DESKTOP_PAGE_IDS = ("shortcuts", "extensions", "help")
PAGE_IDS = (*GOSHOS_PAGE_IDS, *DESKTOP_PAGE_IDS)

_ALIASES = {
    "preferences": "appearance",
    "pref": "appearance",
    "general": "appearance",
    "launcher": "appearance",
    "chrome": "appearance",
    "web": "web-search",
    "websearch": "web-search",
    "web_search": "web-search",
    "keyboard": "shortcut",
    "hotkey": "shortcut",
}


def normalize_prefs_page(page: str | None) -> str | None:
    """Return a PAGE_IDS key, or None to keep the window's default (Shortcut)."""
    if not page:
        return None
    key = page.strip().lower().replace(" ", "-").replace("_", "-")
    mapped = _ALIASES.get(key, key)
    if mapped in PAGE_IDS:
        return mapped
    return None
