"""GTK 3/4 bookmark files, loaded off the first paint like goshos bookmarksSearch.js."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ulauncher import paths
from ulauncher.modes.launcher.paths import (
    canonicalize_file_uri,
    canonicalize_launch_uri,
    collapse_home,
    expand_path,
    file_uri_from_absolute,
    path_from_file_uri,
)
from ulauncher.modes.launcher.urls import is_unsafe_launch_uri
from ulauncher.modes.launcher.word_match import path_matches_query, text_matches_query

BOOKMARK_FILES = (
    Path(paths.XDG_CONFIG_HOME) / "gtk-3.0" / "bookmarks",
    Path(paths.XDG_CONFIG_HOME) / "gtk-4.0" / "bookmarks",
)


class _BookmarkLookup:
    rows: list[dict] | None = None
    loading = False
    on_ready: Callable[[], None] | None = None
    load_id = 0
    pending_finish: Callable[[], None] | None = None


_bookmark_lookup = _BookmarkLookup()


def normalize_bookmark_uri(uri: str, home: str | None = None) -> str:
    uri = uri.strip()
    if not uri:
        return ""
    if is_unsafe_launch_uri(uri):
        return ""
    if uri.startswith("/"):
        return canonicalize_file_uri(file_uri_from_absolute(uri))
    if uri == "~" or uri.startswith("~/"):
        return canonicalize_file_uri(file_uri_from_absolute(expand_path(uri, home)))
    if uri.lower().startswith("file:"):
        return canonicalize_file_uri(uri)
    return canonicalize_launch_uri(uri)


def parse_gtk_bookmarks(text: str, home: str | None = None) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        space = line.find(" ")
        raw_uri = line if space == -1 else line[:space]
        label = "" if space == -1 else line[space + 1 :].strip()
        uri = normalize_bookmark_uri(raw_uri, home)
        if not uri or uri in seen:
            continue
        seen.add(uri)
        rows.append({"uri": uri, "title": bookmark_title(uri, label)})
    return rows


def merge_bookmark_files(texts: list[str], home: str | None = None) -> list[dict]:
    return parse_gtk_bookmarks("\n".join(texts), home)


def host_from_uri(uri: str) -> str:
    from ulauncher.modes.launcher.recents import remote_host_from_uri

    return remote_host_from_uri(uri)


def bookmark_title(uri: str, label: str = "") -> str:
    if label:
        return label
    from ulauncher.modes.launcher.recents import basename_from_uri

    base = basename_from_uri(uri)
    if base and base != uri:
        return base
    host = host_from_uri(uri)
    if host:
        return host
    return uri


def bookmark_description(uri: str, home: str | None = None) -> str:
    path = path_from_file_uri(uri)
    if path:
        return collapse_home(path, home)
    return uri


def bookmark_icon(uri: str) -> str:
    if uri.lower().startswith("file:"):
        return "folder-symbolic"
    return "network-server-symbolic"


def _described(rows: list[dict], home: str | None = None) -> list[dict]:
    return [
        {
            "uri": row["uri"],
            "title": row["title"],
            "description": bookmark_description(row["uri"], home),
            "icon": bookmark_icon(row["uri"]),
        }
        for row in rows
    ]


def _read_bookmark_texts_sync() -> list[str]:
    texts: list[str] = []
    for path in BOOKMARK_FILES:
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        else:
            texts.append("")
    return texts


def load_bookmarks() -> list[dict]:
    return _described(merge_bookmark_files(_read_bookmark_texts_sync()))


def bookmark_matches(title: str, description: str, query: str, uri: str = "") -> bool:
    """Match a bookmark row by its title, its path, or - for a remote share - its host.

    A remote bookmark's description is the whole URI, and path_matches_query only matches at a
    word start over " -_./", so `sftp://alice@nas.local/srv` was reachable by "alice" but not by
    "nas". The host is matched as its own needle.
    """
    if len(query) == 0:
        return False
    host = host_from_uri(uri) if uri else ""

    def matches(needle: str) -> bool:
        if text_matches_query(title, needle) or path_matches_query(description, needle):
            return True
        return bool(host) and text_matches_query(host, needle)

    if matches(query):
        return True
    words = [word for word in query.lower().split() if word]
    if len(words) < 2:
        return False
    return all(matches(word) for word in words)


def match_bookmarks(query: str, rows: list[dict] | None = None, limit: int = 6) -> list[dict]:
    if limit <= 0:
        return []
    if rows is None:
        cached = _bookmark_lookup.rows
        if cached is None:
            return []
        rows = _described(cached)
    results: list[dict] = []
    for row in rows:
        if bookmark_matches(row["title"], row.get("description") or "", query, row.get("uri") or ""):
            results.append(row)
        if len(results) >= limit:
            break
    return results


def bookmarks_are_ready() -> bool:
    return _bookmark_lookup.rows is not None


def search_bookmarks(query: str, limit: int = 6) -> list[dict]:
    if _bookmark_lookup.rows is None:
        return []
    return match_bookmarks(query, _described(_bookmark_lookup.rows), limit)


def invalidate_bookmarks() -> None:
    _bookmark_lookup.rows = None
    _bookmark_lookup.loading = False
    _bookmark_lookup.on_ready = None
    _bookmark_lookup.pending_finish = None
    _bookmark_lookup.load_id += 1


def _flush_ready() -> None:
    callback = _bookmark_lookup.on_ready
    _bookmark_lookup.on_ready = None
    if callback:
        callback()


def _apply_texts(texts: list[str], load_id: int) -> None:
    if load_id != _bookmark_lookup.load_id:
        return
    if _bookmark_lookup.rows is not None:
        return
    _bookmark_lookup.rows = merge_bookmark_files(texts)
    _bookmark_lookup.loading = False
    _bookmark_lookup.pending_finish = None
    _flush_ready()


def _start_load() -> None:
    load_id = _bookmark_lookup.load_id
    _bookmark_lookup.loading = True

    def finish_sync() -> None:
        _apply_texts(_read_bookmark_texts_sync(), load_id)

    _bookmark_lookup.pending_finish = finish_sync
    # The bookmark files are tiny; read them on the next main-loop turn so the
    # first paint stays synchronous and the ready callback stays async.
    from ulauncher.utils import scheduling

    def _load_deferred() -> None:
        if load_id != _bookmark_lookup.load_id:
            return
        finish_sync()

    scheduling.run_when_idle(_load_deferred)


def ensure_bookmarks(on_ready: Callable[[], None]) -> None:
    if _bookmark_lookup.rows is not None:
        return
    _bookmark_lookup.on_ready = on_ready
    if not _bookmark_lookup.loading:
        _start_load()


def flush_bookmarks_lookup() -> None:
    finish = _bookmark_lookup.pending_finish
    _bookmark_lookup.pending_finish = None
    if finish:
        finish()
