"""Recently used files from recently-used.xbel."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse

from ulauncher.modes.launcher.paths import canonicalize_launch_uri, collapse_home, path_from_file_uri
from ulauncher.modes.launcher.word_match import path_matches_query, text_matches_query

XBEL = Path.home() / ".local" / "share" / "recently-used.xbel"
REMOTE_SCHEMES = frozenset({"sftp", "smb", "ftp", "dav", "davs"})
SKIP_SCHEMES = frozenset({"http", "https", "javascript", "data"})


def usable_recent_uri(href: str) -> str:
    text = (href or "").strip()
    if not text or ":" not in text:
        return ""
    scheme, rest = text.split(":", 1)
    scheme = scheme.lower()
    if scheme in SKIP_SCHEMES:
        return ""
    # goshos requires authority slashes so file:javascript: never looks like a path
    if not rest.startswith("//"):
        return ""
    if scheme != "file" and scheme not in REMOTE_SCHEMES:
        return ""
    if "javascript:" in text.lower():
        return ""
    return canonicalize_launch_uri(text)


def parse_xbel(text: str) -> list[dict]:
    rows: list[dict] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return rows
    for bookmark in root.iter():
        if not bookmark.tag.endswith("bookmark"):
            continue
        href = (bookmark.attrib.get("href") or "").strip()
        if not href:
            continue
        uri = usable_recent_uri(href)
        if not uri:
            continue
        path = path_from_file_uri(uri)
        if path:
            if not Path(path).exists():
                continue
            title = Path(path).name or path
            description = collapse_home(str(Path(path).parent))
        else:
            parsed = urlparse(uri)
            title = Path(unquote(parsed.path)).name or parsed.hostname or uri
            description = parsed.hostname or uri
        rows.append(
            {
                "uri": uri,
                "title": title,
                "description": description,
                "icon": "text-x-generic",
            }
        )
    return rows


def load_recents(limit: int = 50) -> list[dict]:
    if not XBEL.is_file():
        return []
    return parse_xbel(XBEL.read_text(encoding="utf-8", errors="replace"))[:limit]


def recent_file_matches(name: str, folder: str, query: str) -> bool:
    if not query:
        return True
    if text_matches_query(name, query) or path_matches_query(folder, query):
        return True
    words = [word for word in query.lower().split() if word]
    if len(words) < 2:
        return False
    return all(text_matches_query(name, word) or path_matches_query(folder, word) for word in words)


def match_recents(query: str, rows: list[dict] | None = None, limit: int = 6) -> list[dict]:
    rows = rows if rows is not None else load_recents()
    if not query.strip():
        return rows[:limit]
    results: list[dict] = []
    for row in rows:
        if recent_file_matches(row["title"], row["description"], query):
            results.append(row)
        if len(results) >= limit:
            break
    return results
