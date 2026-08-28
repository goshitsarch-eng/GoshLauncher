"""Recently-used.xbel search, loaded off the first paint like goshos recentFilesSearch.js."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from ulauncher import paths
from ulauncher.modes.launcher.paths import (
    canonicalize_launch_uri,
    collapse_home,
    decode_uri_component_safe,
    path_from_file_uri,
)
from ulauncher.modes.launcher.word_match import path_matches_query, text_matches_query

XBEL = Path(paths.XDG_DATA_HOME) / "recently-used.xbel"
REMOTE_SCHEMES = frozenset({"sftp", "smb", "ftp", "dav", "davs"})
SKIP_SCHEMES = frozenset({"http", "https", "javascript", "data"})
# goshos recentXbel.js: require authority slashes so file:javascript: never looks like a path
HREF_RE = re.compile(r"""href\s*=\s*["']((?:file|sftp|ftp|smb|davs?)://[^"']+)["']""", re.IGNORECASE)
BOOKMARK_RE = re.compile(r"<bookmark\b[^>]*>", re.IGNORECASE)
# GLib writes these as RFC 3339 UTC, which sorts correctly as text. Older files use a plain
# integer epoch, which sorts correctly too but never against a timestamp, so they are kept apart.
STAMP_RE = re.compile(r"""\b(?:modified|visited|added)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
HOST_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^/@]+@)?([^/:?#]+)")
RECENT_EXISTS_BUDGET_MS = 800
EXT_ICONS = {
    "pdf": "x-office-document-symbolic",
    "doc": "x-office-document-symbolic",
    "docx": "x-office-document-symbolic",
    "odt": "x-office-document-symbolic",
    "txt": "text-x-generic-symbolic",
    "md": "text-x-generic-symbolic",
    "png": "image-x-generic-symbolic",
    "jpg": "image-x-generic-symbolic",
    "jpeg": "image-x-generic-symbolic",
    "gif": "image-x-generic-symbolic",
    "svg": "image-x-generic-symbolic",
    "webp": "image-x-generic-symbolic",
    "mp3": "audio-x-generic-symbolic",
    "wav": "audio-x-generic-symbolic",
    "flac": "audio-x-generic-symbolic",
    "mp4": "video-x-generic-symbolic",
    "mkv": "video-x-generic-symbolic",
    "webm": "video-x-generic-symbolic",
    "zip": "package-x-generic-symbolic",
    "tar": "package-x-generic-symbolic",
    "gz": "package-x-generic-symbolic",
    "html": "text-html-symbolic",
    "htm": "text-html-symbolic",
}


class _RecentLookup:
    uris: list[str] | None = None
    loading = False
    on_ready: Callable[[], None] | None = None
    load_id = 0
    pending_finish: Callable[[], None] | None = None
    timeout: Any = None


_recent_lookup = _RecentLookup()


def unescape_xml(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def recent_stamp(bookmark_tag: str) -> str:
    """The newest timestamp on one <bookmark> tag, or "" when it carries none."""
    return max((match.group(1) for match in STAMP_RE.finditer(bookmark_tag)), default="")


def parse_recent_xbel(text: str) -> list[str]:
    """URIs newest first.

    recently-used.xbel is stored in whatever order GLib last wrote it, not by recency, so a list
    titled "Recent files" has to sort on the bookmark's own modified/visited/added stamps. Entries
    with no stamp keep their file order behind the stamped ones (the sort is stable).
    """
    if not text:
        return []
    stamped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag_match in BOOKMARK_RE.finditer(text):
        tag = tag_match.group(0)
        href_match = HREF_RE.search(tag)
        if not href_match:
            continue
        uri = unescape_xml(href_match.group(1))
        if uri in seen:
            continue
        seen.add(uri)
        stamped.append((recent_stamp(tag), uri))
    stamped.sort(key=lambda item: item[0], reverse=True)
    return [uri for _stamp, uri in stamped]


def usable_recent_uri(href: str) -> str:
    text = (href or "").strip()
    if not text or ":" not in text:
        return ""
    scheme, rest = text.split(":", 1)
    scheme = scheme.lower()
    if scheme in SKIP_SCHEMES:
        return ""
    if not rest.startswith("//"):
        return ""
    if scheme != "file" and scheme not in REMOTE_SCHEMES:
        return ""
    if "javascript:" in text.lower():
        return ""
    return canonicalize_launch_uri(text)


def basename_from_uri(uri: str) -> str:
    raw = uri.rsplit("/", maxsplit=1)[-1] if uri else ""
    return decode_uri_component_safe(raw) or uri


def parent_path_from_file_uri(uri: str) -> str:
    path = path_from_file_uri(uri)
    if not path:
        return ""
    slash = path.rfind("/")
    if slash < 0:
        return ""
    if slash == 0:
        return "/"
    return path[:slash]


def remote_host_from_uri(uri: str) -> str:
    match = HOST_RE.match(uri or "")
    return match.group(1) if match else ""


def icon_for_basename(name: str) -> str:
    dot = name.rfind(".")
    if dot < 1 or dot == len(name) - 1:
        return "document-open-recent-symbolic"
    return EXT_ICONS.get(name[dot + 1 :].lower(), "document-open-recent-symbolic")


def recent_exists_should_settle(pending: int, elapsed_ms: float, budget_ms: float = RECENT_EXISTS_BUDGET_MS) -> bool:
    return pending <= 0 or elapsed_ms >= budget_ms


def recent_row_from_uri(uri: str, home: str | None = None) -> dict:
    name = basename_from_uri(uri)
    parent = parent_path_from_file_uri(uri)
    if parent:
        folder = collapse_home(parent, home)
    else:
        folder = remote_host_from_uri(uri) or "Recent file"
    return {
        "uri": uri,
        "title": name,
        "description": folder,
        "icon": icon_for_basename(name),
    }


def parse_xbel(text: str) -> list[dict]:
    return [recent_row_from_uri(uri) for uri in parse_recent_xbel(text)]


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


def _rows_from_cache() -> list[dict]:
    uris = _recent_lookup.uris
    if uris is None:
        return []
    home = str(Path.home())
    return [recent_row_from_uri(uri, home) for uri in uris]


def match_recents(query: str, rows: list[dict] | None = None, limit: int = 6) -> list[dict]:
    if limit <= 0:
        return []
    rows = rows if rows is not None else _rows_from_cache()
    if not query.strip():
        return rows[:limit]
    results: list[dict] = []
    for row in rows:
        if recent_file_matches(row["title"], row["description"], query):
            results.append(row)
        if len(results) >= limit:
            break
    return results


def recents_are_ready() -> bool:
    return _recent_lookup.uris is not None


def search_recents(query: str, limit: int = 6) -> list[dict]:
    if _recent_lookup.uris is None:
        return []
    return match_recents(query, _rows_from_cache(), limit)


def _clear_timeout() -> None:
    timeout = _recent_lookup.timeout
    _recent_lookup.timeout = None
    if timeout is not None:
        timeout.cancel()


def invalidate_recent_files() -> None:
    _clear_timeout()
    _recent_lookup.uris = None
    _recent_lookup.loading = False
    _recent_lookup.on_ready = None
    _recent_lookup.pending_finish = None
    _recent_lookup.load_id += 1


def _flush_ready() -> None:
    callback = _recent_lookup.on_ready
    _recent_lookup.on_ready = None
    if callback:
        callback()


def _apply_uris(uris: list[str], load_id: int) -> None:
    if load_id != _recent_lookup.load_id or _recent_lookup.uris is not None:
        return
    _clear_timeout()
    _recent_lookup.uris = [uri for uri in uris if uri]
    _recent_lookup.loading = False
    _recent_lookup.pending_finish = None
    _flush_ready()





def _uri_exists_sync(uri: str) -> bool:
    path = path_from_file_uri(uri)
    if path:
        return Path(path).exists()
    # tests and flush must not block on network mounts; live Gio still probes remotes
    scheme = uri.split(":", 1)[0].lower()
    return scheme in REMOTE_SCHEMES


def _read_xbel_sync() -> str:
    if not XBEL.is_file():
        return ""
    return XBEL.read_text(encoding="utf-8", errors="replace")


def _keep_existing_sync(uris: list[str]) -> list[str]:
    kept: list[str] = []
    for uri in uris:
        canon = canonicalize_launch_uri(uri)
        if canon and _uri_exists_sync(canon):
            kept.append(canon)
    return kept


def _start_load() -> None:
    load_id = _recent_lookup.load_id
    _recent_lookup.loading = True

    def finish_sync() -> None:
        if _recent_lookup.uris is not None:
            return
        _apply_uris(_keep_existing_sync(parse_recent_xbel(_read_xbel_sync())), load_id)

    _recent_lookup.pending_finish = finish_sync
    # Deferred sync read: local paths are checked with a plain stat, remote URIs are
    # kept without probing (see _uri_exists_sync) - a network probe here could block
    # search on an unreachable mount, and the open path handles unreachable shares.
    from ulauncher.utils import scheduling

    def _load_deferred() -> None:
        if load_id != _recent_lookup.load_id or _recent_lookup.uris is not None:
            return
        finish_sync()

    scheduling.run_when_idle(_load_deferred)


def ensure_recent_files(on_ready: Callable[[], None]) -> None:
    if _recent_lookup.uris is not None:
        return
    _recent_lookup.on_ready = on_ready
    if not _recent_lookup.loading:
        _start_load()


def flush_recents_lookup() -> None:
    finish = _recent_lookup.pending_finish
    _recent_lookup.pending_finish = None
    if finish:
        finish()
