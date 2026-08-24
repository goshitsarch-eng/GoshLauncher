"""Recently-used.xbel search, loaded off the first paint like goshos recentFilesSearch.js."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from ulauncher.modes.launcher.paths import (
    canonicalize_launch_uri,
    collapse_home,
    decode_uri_component_safe,
    path_from_file_uri,
)
from ulauncher.modes.launcher.word_match import path_matches_query, text_matches_query

XBEL = Path.home() / ".local" / "share" / "recently-used.xbel"
REMOTE_SCHEMES = frozenset({"sftp", "smb", "ftp", "dav", "davs"})
SKIP_SCHEMES = frozenset({"http", "https", "javascript", "data"})
# goshos recentXbel.js: require authority slashes so file:javascript: never looks like a path
HREF_RE = re.compile(r"""href\s*=\s*["']((?:file|sftp|ftp|smb|davs?)://[^"']+)["']""", re.IGNORECASE)
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


def parse_recent_xbel(text: str) -> list[str]:
    if not text:
        return []
    uris: list[str] = []
    seen: set[str] = set()
    for match in HREF_RE.finditer(text):
        uri = unescape_xml(match.group(1))
        if uri in seen:
            continue
        seen.add(uri)
        uris.append(uri)
    return uris


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


def _decode_contents(source: Any, result: Any) -> str:
    try:
        finished = source.load_contents_finish(result)
    except Exception:
        return ""
    contents: Any = finished
    if isinstance(finished, tuple):
        contents = finished[1] if isinstance(finished[0], bool) else finished[0]
    if isinstance(contents, memoryview):
        contents = contents.tobytes()
    if isinstance(contents, bytes):
        return contents.decode("utf-8", errors="replace")
    return str(contents or "")


def _exists_finished(source: Any, result: Any) -> bool:
    try:
        return bool(source.query_exists_finish(result))
    except Exception:
        return False


def _query_exists_async(file: Any, glib: Any, callback: Callable[[Any, Any], None]) -> None:
    try:
        file.query_exists_async(glib.PRIORITY_DEFAULT, None, callback)
    except TypeError:
        file.query_exists_async(None, callback)


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


def _start_exists(load_id: int, uris: list[str]) -> None:
    if load_id != _recent_lookup.load_id or _recent_lookup.uris is not None:
        return
    if not uris:
        _apply_uris([], load_id)
        return

    kept: list[str] = [""] * len(uris)
    pending = len(uris)
    started = time.monotonic()
    settled = False

    def settle() -> None:
        nonlocal settled
        if settled or load_id != _recent_lookup.load_id:
            return
        settled = True
        _apply_uris(kept, load_id)

    def finish_sync() -> None:
        if _recent_lookup.uris is not None:
            return
        _apply_uris(_keep_existing_sync(uris), load_id)

    _recent_lookup.pending_finish = finish_sync
    try:
        from ulauncher.gi import Gio, GLib
    except Exception:
        finish_sync()
        return

    try:
        from ulauncher.utils import scheduling

        _recent_lookup.timeout = scheduling.timer(RECENT_EXISTS_BUDGET_MS / 1000.0, settle)
    except Exception:
        _recent_lookup.timeout = None

    for index, raw in enumerate(uris):
        uri = canonicalize_launch_uri(raw)
        if not uri:
            pending -= 1
            if recent_exists_should_settle(pending, (time.monotonic() - started) * 1000):
                settle()
            continue
        file = Gio.File.new_for_uri(uri)

        def on_exists(src: Any, res: Any, slot: int = index, checked: str = uri) -> None:
            nonlocal pending
            exists = _exists_finished(src, res)
            if load_id != _recent_lookup.load_id:
                return
            if exists:
                kept[slot] = checked
            pending -= 1
            elapsed_ms = (time.monotonic() - started) * 1000
            if recent_exists_should_settle(pending, elapsed_ms):
                settle()

        try:
            _query_exists_async(file, GLib, on_exists)
        except Exception:
            if _uri_exists_sync(uri):
                kept[index] = uri
            pending -= 1
            if recent_exists_should_settle(pending, (time.monotonic() - started) * 1000):
                settle()


def _start_load() -> None:
    load_id = _recent_lookup.load_id
    _recent_lookup.loading = True

    def finish_sync() -> None:
        if _recent_lookup.uris is not None:
            return
        _apply_uris(_keep_existing_sync(parse_recent_xbel(_read_xbel_sync())), load_id)

    _recent_lookup.pending_finish = finish_sync
    try:
        from ulauncher.gi import Gio, GLib
    except Exception:
        finish_sync()
        return

    file = Gio.File.new_for_path(str(XBEL))

    def on_exists(src: Any, exists_res: Any) -> None:
        exists = _exists_finished(src, exists_res)
        if load_id != _recent_lookup.load_id or _recent_lookup.uris is not None:
            return
        if not exists:
            _apply_uris([], load_id)
            return

        def on_loaded(loaded: Any, load_res: Any) -> None:
            if load_id != _recent_lookup.load_id or _recent_lookup.uris is not None:
                return
            _start_exists(load_id, parse_recent_xbel(_decode_contents(loaded, load_res)))

        try:
            src.load_contents_async(None, on_loaded)
        except Exception:
            _apply_uris([], load_id)

    try:
        _query_exists_async(file, GLib, on_exists)
    except Exception:
        finish_sync()


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
