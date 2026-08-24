"""Web search engines and fallback rows."""

from __future__ import annotations

from urllib.parse import quote_plus

SEARCH_ENGINES = [
    {"id": "google", "label": "Google", "url": "https://www.google.com/search?q="},
    {"id": "duckduckgo", "label": "DuckDuckGo", "url": "https://duckduckgo.com/?q="},
    {"id": "brave", "label": "Brave", "url": "https://search.brave.com/search?q="},
    {"id": "bing", "label": "Bing", "url": "https://www.bing.com/search?q="},
    {"id": "startpage", "label": "Startpage", "url": "https://www.startpage.com/do/search?q="},
    {"id": "ecosia", "label": "Ecosia", "url": "https://www.ecosia.org/search?q="},
    {"id": "qwant", "label": "Qwant", "url": "https://www.qwant.com/?q="},
    {"id": "kagi", "label": "Kagi", "url": "https://kagi.com/search?q="},
    {"id": "wikipedia", "label": "Wikipedia", "url": "https://en.wikipedia.org/w/index.php?search="},
]


def engine_prefs_search_text() -> str:
    return ", ".join(engine["label"] for engine in SEARCH_ENGINES)


def get_engine(engine_id: str) -> dict:
    for engine in SEARCH_ENGINES:
        if engine["id"] == engine_id:
            return engine
    return SEARCH_ENGINES[0]


def search_url(query: str, engine_id: str) -> str:
    engine = get_engine(engine_id)
    return engine["url"] + quote_plus(query)


def web_result(query: str, engine_id: str) -> dict:
    engine = get_engine(engine_id)
    return {
        "title": f'Search {engine["label"]} for "{query}"',
        "description": f"Open {engine['label']} in your browser",
        "url": search_url(query, engine_id),
        "icon": "web-browser-symbolic",
    }
