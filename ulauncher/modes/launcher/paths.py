"""Open ~/ ./ and absolute filesystem paths."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote

from ulauncher.modes.launcher.plan import is_path_query

TERMINALS = (
    "xdg-terminal-exec",
    "ptyxis",
    "kgx",
    "gnome-terminal",
    "ghostty",
    "kitty",
    "alacritty",
    "foot",
    "wezterm",
    "tilix",
    "blackbox-terminal",
    "blackbox",
)

_UNSAFE_SCHEMES = frozenset({"javascript", "data", "vbscript"})
_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_SCHEME_FUZZ_RE = re.compile(r"[\0\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_REMOTE_URI_RE = re.compile(r"^(sftp|ftp|smb|davs?)://([^/]+)(/[^?#]*)?([?#].*)?$", re.IGNORECASE)
_FILE_AUTH_RE = re.compile(r"^(file)://([^/]+)(/[^?#]*)?([?#].*)?$", re.IGNORECASE)


def normalize_absolute(path: str) -> str:
    if not path.startswith("/"):
        return path
    parts: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def expand_path(query: str, home: str | None = None) -> str:
    text = query.strip()
    home_dir = home if home is not None else str(Path.home())
    if text == "~":
        raw = home_dir
    elif text.startswith("~/"):
        raw = f"{home_dir}/{text[2:]}"
    elif text == ".":
        raw = home_dir
    elif text.startswith("./"):
        raw = f"{home_dir}/{text[2:]}"
    elif text == "..":
        raw = f"{home_dir}/.."
    elif text.startswith("../"):
        raw = f"{home_dir}/{text}"
    else:
        return text
    return normalize_absolute(raw)


def expand_home_argv(argv: list[str], home: str | None = None) -> list[str]:
    return [expand_path(arg, home) for arg in argv]


def resolve_spawn_path(path: str, home: str | None = None) -> str:
    if not path:
        return ""
    if "/" not in path:
        return path
    home_dir = home if home is not None else str(Path.home())
    expanded = expand_path(path, home_dir)
    if expanded.startswith("/"):
        return normalize_absolute(expanded)
    return normalize_absolute(f"{home_dir}/{path}")


def resolve_command_argv(argv: list[str], home: str | None = None) -> list[str]:
    expanded = expand_home_argv(argv, home)
    if not expanded:
        return expanded
    return [resolve_spawn_path(expanded[0], home), *expanded[1:]]


def collapse_home(path: str, home: str | None = None) -> str:
    home_dir = home if home is not None else str(Path.home())
    if path == home_dir:
        return "~"
    if path.startswith(home_dir + os.sep):
        return "~" + path[len(home_dir) :]
    return path


def decode_uri_component_safe(text: str) -> str:
    # goshos decodeURIComponent throws on latin-1 percent bytes such as %E9.
    # Python unquote replaces those; strict keeps the original href instead.
    if not text:
        return ""
    safe = _PERCENT_RE.sub("%25", text)
    try:
        return unquote(safe, errors="strict")
    except UnicodeDecodeError:
        return safe


def file_uri_from_absolute(path: str) -> str:
    return "file://" + "/".join(quote(part) for part in path.split("/"))


def path_from_file_uri(uri: str) -> str:
    href = uri.split("#", 1)[0].split("?", 1)[0]
    if not href.lower().startswith("file://"):
        return ""
    raw = href[len("file://") :]
    raw_lower = raw.lower()
    if raw_lower == "localhost" or raw_lower.startswith("localhost/"):
        raw = raw[len("localhost") :]
    if not raw.startswith("/"):
        return ""
    safe = _PERCENT_RE.sub("%25", raw)
    try:
        return unquote(safe, errors="strict")
    except UnicodeDecodeError:
        return ""


def _encode_uri_path_part(part: str) -> str:
    if not part:
        return ""
    safe = _PERCENT_RE.sub("%25", part)
    try:
        return quote(unquote(safe, errors="strict"), safe="")
    except UnicodeDecodeError:
        return safe


def _encode_authority_uri(uri: str, pattern: re.Pattern) -> str:
    match = pattern.match(uri or "")
    if not match:
        return uri
    path = match.group(3) or ""
    if not path:
        return uri
    encoded = "/".join(_encode_uri_path_part(part) for part in path.split("/"))
    return f"{match.group(1)}://{match.group(2)}{encoded}{match.group(4) or ''}"


def canonicalize_file_uri(uri: str) -> str:
    if not uri or not uri.lower().startswith("file:"):
        return uri
    path = path_from_file_uri(uri)
    if path:
        return file_uri_from_absolute(path)
    return _encode_authority_uri(uri, _FILE_AUTH_RE)


def canonicalize_remote_uri(uri: str) -> str:
    return _encode_authority_uri(uri, _REMOTE_URI_RE)


def canonicalize_launch_uri(uri: str) -> str:
    if not uri:
        return uri
    scheme = _SCHEME_FUZZ_RE.sub("", uri).strip().split(":", 1)[0].lower()
    if scheme in _UNSAFE_SCHEMES:
        return ""
    if uri.lower().startswith("file:"):
        return canonicalize_file_uri(uri)
    if _REMOTE_URI_RE.match(uri):
        return canonicalize_remote_uri(uri)
    return uri


def path_row_meta(trimmed: str, resolved: str, kind: str, home: str | None = None) -> dict:
    row_id = resolved or trimmed
    if kind == "missing":
        return {
            "type": "path",
            "path": resolved,
            "kind": "missing",
            "title": trimmed,
            "description": "Path not found",
            "icon": "dialog-warning-symbolic",
            "id": row_id,
            "activatable": False,
            "exists": False,
            "is_dir": False,
            "checking": False,
            "in_terminal": False,
        }
    if kind == "pending":
        return {
            "type": "path",
            "path": resolved,
            "kind": "pending",
            "title": collapse_home(resolved, home),
            "description": "Checking path",
            "icon": "folder-symbolic",
            "id": row_id,
            "activatable": False,
            "exists": False,
            "is_dir": False,
            "checking": True,
            "in_terminal": False,
        }
    is_dir = kind == "directory"
    if is_dir:
        icon = "folder-symbolic"
    else:
        from ulauncher.modes.launcher.recents import icon_for_basename

        icon = icon_for_basename(Path(resolved).name)
    return {
        "type": "path",
        "path": resolved,
        "kind": "directory" if is_dir else "file",
        "title": collapse_home(resolved, home),
        "description": "Open path",
        "icon": icon,
        "id": row_id,
        "exists": True,
        "is_dir": is_dir,
        "checking": False,
        "in_terminal": False,
    }


def path_rows(
    trimmed: str,
    resolved: str,
    kind: str,
    home: str | None = None,
    find_in_path: Callable[[str], str | None] | None = None,
) -> list[dict]:
    rows = [path_row_meta(trimmed, resolved, kind, home)]
    if kind != "directory":
        return rows
    if not terminal_command(resolved, find_in_path=find_in_path):
        return rows
    term = terminal_row_meta(resolved, home)
    term["exists"] = True
    term["checking"] = False
    term["is_dir"] = True
    rows.append(term)
    return rows


def match_path(query: str, kind: str | None = None) -> dict | None:
    if not is_path_query(query):
        return None
    resolved = expand_path(query)
    if kind is None:
        kind = _stat_path_kind(resolved)
    return path_row_meta(query.strip(), resolved, kind)


def terminal_spec(find_in_path: Any | None = None) -> dict | None:
    if find_in_path is None:
        from ulauncher.modes.launcher.gio_launch import find_in_user_path

        find_in_path = find_in_user_path
    if find_in_path("xdg-terminal-exec"):
        return {"argv": ["xdg-terminal-exec"], "use_directory_cwd": True}
    if find_in_path("konsole"):
        return {"argv": ["konsole"], "working_directory_flag": "--workdir"}
    if find_in_path("ptyxis"):
        return {"argv": ["ptyxis", "--new-window"], "working_directory_flag": "--working-directory"}
    if find_in_path("kgx"):
        return {"argv": ["kgx"], "working_directory_flag": "--working-directory"}
    if find_in_path("gnome-terminal"):
        return {"argv": ["gnome-terminal"], "working_directory_flag": "--working-directory"}
    if find_in_path("ghostty"):
        return {"argv": ["ghostty"], "working_directory_flag": "--working-directory"}
    if find_in_path("kitty"):
        return {"argv": ["kitty"], "working_directory_flag": "--directory"}
    if find_in_path("alacritty"):
        return {"argv": ["alacritty"], "working_directory_flag": "--working-directory"}
    if find_in_path("foot"):
        return {"argv": ["foot"], "working_directory_flag": "--working-directory"}
    if find_in_path("wezterm"):
        return {"argv": ["wezterm", "start"], "working_directory_flag": "--cwd"}
    if find_in_path("tilix"):
        return {"argv": ["tilix"], "working_directory_flag": "--working-directory"}
    if find_in_path("blackbox-terminal"):
        return {"argv": ["blackbox-terminal"], "working_directory_flag": "--working-directory"}
    if find_in_path("blackbox"):
        return {"argv": ["blackbox"], "working_directory_flag": "--working-directory"}
    return None


def terminal_command(directory: str, find_in_path: Callable[[str], str | None] | None = None) -> dict | None:
    spec = terminal_spec(find_in_path)
    if not spec or not directory:
        return None
    if spec.get("use_directory_cwd"):
        return {"argv": list(spec["argv"]), "cwd": directory}
    flag = spec["working_directory_flag"]
    return {"argv": [*list(spec["argv"]), f"{flag}={directory}"], "cwd": None}


def terminal_row_meta(directory: str, home: str | None = None, kind: str | None = None) -> dict:
    return {
        "type": kind or "path",
        "title": "Open in Terminal",
        "description": collapse_home(directory, home),
        "icon": "utilities-terminal-symbolic",
        "id": f"terminal:{directory}",
        "path": directory,
        "in_terminal": True,
    }


def first_terminal() -> str | None:
    from ulauncher.modes.launcher.gio_launch import find_in_user_path

    for name in TERMINALS:
        found = find_in_user_path(name)
        if found:
            return found
    return None


class _PathLookup:
    query = ""
    rows: list[dict] | None = None
    resolved = False
    on_ready: Callable[[], None] | None = None
    load_id = 0
    pending_finish: Callable[[], None] | None = None


_path_lookup = _PathLookup()


def _stat_path_kind(resolved: str) -> str:
    path = Path(resolved)
    if not path.exists():
        return "missing"
    if path.is_dir():
        return "directory"
    return "file"


def _apply_path_kind(trimmed: str, resolved: str, kind: str, load_id: int) -> None:
    if load_id != _path_lookup.load_id:
        return
    if _path_lookup.resolved and _path_lookup.query == trimmed:
        return
    home = str(Path.home())
    _path_lookup.rows = path_rows(trimmed, resolved, kind, home)
    _path_lookup.resolved = True
    _path_lookup.pending_finish = None
    callback = _path_lookup.on_ready
    _path_lookup.on_ready = None
    if callback:
        callback()


def _start_path_stat(resolved: str, on_kind: Callable[[str], None]) -> None:
    # Deferred to the next main-loop turn to keep the callback contract async
    # (callers arm their lookup state before the result may arrive).
    from ulauncher.utils import scheduling

    scheduling.run_when_idle(lambda: on_kind(_stat_path_kind(resolved)))


def invalidate_path_lookup() -> None:
    _path_lookup.query = ""
    _path_lookup.rows = None
    _path_lookup.resolved = False
    _path_lookup.on_ready = None
    _path_lookup.pending_finish = None
    _path_lookup.load_id += 1


def path_is_resolved(query: str) -> bool:
    trimmed = query.strip()
    return _path_lookup.query == trimmed and _path_lookup.resolved


def search_path(query: str) -> list[dict]:
    trimmed = query.strip()
    if not is_path_query(trimmed):
        return []
    resolved = expand_path(trimmed)
    if not resolved:
        return []
    if path_is_resolved(trimmed) and _path_lookup.rows is not None:
        return list(_path_lookup.rows)
    return path_rows(trimmed, resolved, "pending")


def ensure_path(query: str, on_ready: Callable[[], None]) -> None:
    trimmed = query.strip()
    if not is_path_query(trimmed):
        return
    if _path_lookup.query == trimmed and _path_lookup.resolved:
        return
    _path_lookup.on_ready = on_ready
    if _path_lookup.query == trimmed and not _path_lookup.resolved:
        return
    _path_lookup.load_id += 1
    load_id = _path_lookup.load_id
    _path_lookup.query = trimmed
    _path_lookup.resolved = False
    resolved = expand_path(trimmed)

    def finish_sync() -> None:
        _apply_path_kind(trimmed, resolved, _stat_path_kind(resolved), load_id)

    _path_lookup.pending_finish = finish_sync
    _start_path_stat(resolved, lambda kind: _apply_path_kind(trimmed, resolved, kind, load_id))


def flush_path_lookup() -> None:
    finish = _path_lookup.pending_finish
    _path_lookup.pending_finish = None
    if finish:
        finish()
