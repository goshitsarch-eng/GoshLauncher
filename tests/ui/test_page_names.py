from __future__ import annotations

from ulauncher.ui.preferences.page_names import GOSHOS_PAGE_IDS, PAGE_IDS, normalize_prefs_page


def test_goshos_page_order_matches_prefs_js() -> None:
    assert GOSHOS_PAGE_IDS == ("shortcut", "appearance", "features", "web-search", "about")


def test_normalize_prefs_page_aliases() -> None:
    assert normalize_prefs_page(None) is None
    assert normalize_prefs_page("") is None
    assert normalize_prefs_page("about") == "about"
    assert normalize_prefs_page("About") == "about"
    assert normalize_prefs_page("preferences") == "appearance"
    assert normalize_prefs_page("web") == "web-search"
    assert normalize_prefs_page("web search") == "web-search"
    assert normalize_prefs_page("web_search") == "web-search"
    assert normalize_prefs_page("extensions") == "extensions"
    assert normalize_prefs_page("shortcuts") == "shortcuts"
    assert normalize_prefs_page("desktop") == "desktop"
    assert normalize_prefs_page("help") == "about"
    assert normalize_prefs_page("not-a-page") is None
    assert set(GOSHOS_PAGE_IDS).issubset(PAGE_IDS)
    assert PAGE_IDS == (
        "shortcut",
        "appearance",
        "features",
        "web-search",
        "about",
        "desktop",
        "shortcuts",
        "extensions",
    )
    assert "help" not in PAGE_IDS
