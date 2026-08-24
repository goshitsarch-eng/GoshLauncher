"""GTK 3/4 bookmark files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from ulauncher.modes.launcher.word_match import path_matches_query, text_matches_query

BOOKMARK_FILES = (
    Path.home() / ".config" / "gtk-3.0" / "bookmarks",
    Path.home() / ".config" / "gtk-4.0" / "bookmarks",
)


def _is_unsafe(uri: str) -> bool:
    return uri.lower().split(":", 1)[0] in {"javascript", "data", "vbscript"}


def _file_uri_from_path(path: str) -> str:
    return "file://" + path.replace(" ", "%20")


def normalize_bookmark_uri(uri: str) -> str:
    uri = uri.strip()
    if not uri or _is_unsafe(uri):
        return ""
    if uri.startswith("/"):
        return _file_uri_from_path(uri)
    if uri == "~" or uri.startswith("~/"):
        return _file_uri_from_path(str(Path(uri).expanduser()))
    if uri.lower().startswith("file:"):
        return uri.replace(" ", "%20")
    return uri


def parse_gtk_bookmarks(text: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        space = line.find(" ")
        raw_uri = line if space == -1 else line[:space]
        label = "" if space == -1 else line[space + 1 :].strip()
        uri = normalize_bookmark_uri(raw_uri)
        if not uri or uri in seen:
            continue
        seen.add(uri)
        rows.append({"uri": uri, "title": label or _title_from_uri(uri)})
    return rows


def _title_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        name = Path(path).name
        return name or path or uri
    return parsed.hostname or uri


def bookmark_description(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        home = str(Path.home())
        if path == home:
            return "~"
        if path.startswith(home + "/"):
            return "~" + path[len(home) :]
        return path
    return uri


def load_bookmarks() -> list[dict]:
    chunks: list[str] = []
    for path in BOOKMARK_FILES:
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    rows = parse_gtk_bookmarks("\n".join(chunks))
    for row in rows:
        row["description"] = bookmark_description(row["uri"])
        row["icon"] = "folder" if row["uri"].lower().startswith("file:") else "network-server"
    return rows


def match_bookmarks(query: str, rows: list[dict] | None = None, limit: int = 6) -> list[dict]:
    rows = rows if rows is not None else load_bookmarks()
    results: list[dict] = []
    for row in rows:
        title = row["title"]
        description = row.get("description") or ""
        if text_matches_query(title, query) or path_matches_query(description, query):
            results.append(row)
        elif len(query.split()) >= 2:
            words = [w for w in query.lower().split() if w]
            if words and all(
                text_matches_query(title, word) or path_matches_query(description, word) for word in words
            ):
                results.append(row)
        if len(results) >= limit:
            break
    return results
