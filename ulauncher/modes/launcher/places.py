"""XDG user-folder matching."""

from __future__ import annotations

import os
from pathlib import Path

from ulauncher.modes.launcher.word_match import keyword_matches_query, word_prefix_match

PLACE_CATALOG = [
    {"id": "home", "title": "Home", "keywords": ["home", "~"], "icon": "user-home-symbolic", "env": "HOME"},
    {
        "id": "desktop",
        "title": "Desktop",
        "keywords": ["desktop"],
        "icon": "user-desktop-symbolic",
        "xdg": "XDG_DESKTOP_DIR",
    },
    {
        "id": "documents",
        "title": "Documents",
        "keywords": ["documents", "docs"],
        "icon": "folder-documents-symbolic",
        "xdg": "XDG_DOCUMENTS_DIR",
    },
    {
        "id": "download",
        "title": "Downloads",
        "keywords": ["downloads", "download"],
        "icon": "folder-download-symbolic",
        "xdg": "XDG_DOWNLOAD_DIR",
    },
    {
        "id": "music",
        "title": "Music",
        "keywords": ["music", "audio"],
        "icon": "folder-music-symbolic",
        "xdg": "XDG_MUSIC_DIR",
    },
    {
        "id": "pictures",
        "title": "Pictures",
        "keywords": ["pictures", "photos", "images"],
        "icon": "folder-pictures-symbolic",
        "xdg": "XDG_PICTURES_DIR",
    },
    {
        "id": "videos",
        "title": "Videos",
        "keywords": ["videos", "movies"],
        "icon": "folder-videos-symbolic",
        "xdg": "XDG_VIDEOS_DIR",
    },
    {
        "id": "public",
        "title": "Public",
        "keywords": ["public", "share"],
        "icon": "folder-publicshare-symbolic",
        "xdg": "XDG_PUBLICSHARE_DIR",
    },
    {
        "id": "templates",
        "title": "Templates",
        "keywords": ["templates"],
        "icon": "folder-templates-symbolic",
        "xdg": "XDG_TEMPLATES_DIR",
    },
]


def _xdg_dirs() -> dict[str, str]:
    mapping: dict[str, str] = {"HOME": str(Path.home())}
    conf = Path.home() / ".config" / "user-dirs.dirs"
    if not conf.is_file():
        return mapping
    for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        mapping[key] = os.path.expandvars(value.strip().strip('"'))
    return mapping


def place_path(place: dict, dirs: dict[str, str] | None = None) -> str:
    dirs = dirs or _xdg_dirs()
    if place["id"] == "home":
        return dirs.get("HOME") or str(Path.home())
    env = place.get("xdg")
    if env and dirs.get(env):
        return dirs[env]
    fallback = Path.home() / place["title"]
    return str(fallback) if fallback.exists() else dirs.get("HOME") or str(Path.home())


def place_matches(title: str, keywords: list[str], query: str) -> bool:
    if not query:
        return False
    q = query.lower()
    title_lower = title.lower()
    # a one-letter query must be a prefix so o does not list every folder
    if len(q) == 1:
        if title_lower.startswith(q):
            return True
        return any(keyword.lower().startswith(q) for keyword in keywords)
    if title_lower.startswith(q) or word_prefix_match(title_lower, q):
        return True
    return any(keyword_matches_query(keyword, q) for keyword in keywords)


def match_places(query: str, limit: int = 6) -> list[dict]:
    dirs = _xdg_dirs()
    seen: set[str] = set()
    results: list[dict] = []
    for place in PLACE_CATALOG:
        if not place_matches(place["title"], place["keywords"], query):
            continue
        path = place_path(place, dirs)
        if not path or path in seen:
            continue
        seen.add(path)
        results.append({**place, "path": path})
        if len(results) >= limit:
            break
    return results
