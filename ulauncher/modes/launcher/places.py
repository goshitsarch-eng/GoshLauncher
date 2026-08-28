"""XDG user-folder matching."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, TypedDict

from ulauncher.modes.launcher.word_match import keyword_matches_query, word_prefix_match


class _PlaceRequired(TypedDict):
    id: str
    title: str
    keywords: list[str]
    icon: str


class PlaceEntry(_PlaceRequired, total=False):
    env: str
    xdg: str


PLACE_CATALOG: list[PlaceEntry] = [
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


_PLACE_USER_DIR = {
    "desktop": "DESKTOP",
    "documents": "DOCUMENTS",
    "download": "DOWNLOAD",
    "music": "MUSIC",
    "pictures": "PICTURES",
    "videos": "VIDEOS",
    "public": "PUBLICSHARE",
    "templates": "TEMPLATES",
}


def _glib_place_path(place_id: str) -> str | None:
    """XDG user-dir lookup (the name predates the GLib-free port)."""
    if place_id == "home":
        return str(Path.home())
    name = _PLACE_USER_DIR.get(place_id)
    if not name:
        return None
    from ulauncher.utils.user_dirs import get_user_dir

    return get_user_dir(name)


def place_path(place: PlaceEntry, dirs: dict[str, str] | None = None) -> str:
    if dirs is None:
        glib_path = _glib_place_path(place["id"])
        if glib_path:
            return glib_path
        dirs = _xdg_dirs()
    if place["id"] == "home":
        return dirs.get("HOME") or str(Path.home())
    env = place.get("xdg")
    if env and dirs.get(env):
        return dirs[env]
    # GLib.get_user_special_dir still returns $HOME/Documents when the folder is
    # missing. Mapping that to $HOME made unique-path collapse hide every place.
    return str(Path(dirs.get("HOME") or Path.home()) / place["title"])


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


def match_places(query: str, limit: int = 6, dirs: dict[str, str] | None = None) -> list[dict]:
    mapping = dirs
    seen: set[str] = set()
    results: list[dict] = []
    for place in PLACE_CATALOG:
        if not place_matches(place["title"], place["keywords"], query):
            continue
        path = place_path(place, mapping)
        if not path or path in seen:
            continue
        seen.add(path)
        results.append({**place, "path": path})
        if len(results) >= limit:
            break
    return results


def search_places(
    query: str,
    limit: int = 6,
    home: str | None = None,
    find_in_path: Callable[[str], str | None] | None = None,
    dirs: dict[str, str] | None = None,
) -> list[dict]:
    from ulauncher.modes.launcher.paths import collapse_home, terminal_command, terminal_row_meta

    home_dir = home if home is not None else str(Path.home())
    matches = match_places(query, limit, dirs=dirs)
    rows: list[dict] = []
    for place in matches:
        path = str(place["path"])
        rows.append(
            {
                "kind": "place",
                "title": place["title"],
                "description": collapse_home(path, home_dir),
                "icon": place["icon"],
                "id": place["id"],
                "path": path,
                "in_terminal": False,
            }
        )
    if not matches or len(rows) >= limit:
        return rows
    first_path = str(matches[0]["path"])
    if not terminal_command(first_path, find_in_path=find_in_path):
        return rows
    term = terminal_row_meta(first_path, home_dir, kind="place")
    rows.append(
        {
            "kind": "place",
            "title": term["title"],
            "description": term["description"],
            "icon": term["icon"],
            "id": term["id"],
            "path": first_path,
            "in_terminal": True,
        }
    )
    return rows
