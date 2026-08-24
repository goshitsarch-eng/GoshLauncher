"""Open ~/ ./ and absolute filesystem paths."""

from __future__ import annotations

import os
import re
from pathlib import Path
from shutil import which
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


def collapse_home(path: str, home: str | None = None) -> str:
    home_dir = home if home is not None else str(Path.home())
    if path == home_dir:
        return "~"
    if path.startswith(home_dir + os.sep):
        return "~" + path[len(home_dir) :]
    return path


def decode_uri_component_safe(text: str) -> str:
    if not text:
        return ""
    safe = _PERCENT_RE.sub("%25", text)
    try:
        return unquote(safe)
    except Exception:
        return safe


def file_uri_from_absolute(path: str) -> str:
    return "file://" + "/".join(quote(part) for part in path.split("/"))


def path_from_file_uri(uri: str) -> str:
    href = uri.split("#")[0].split("?")[0]
    if not href.lower().startswith("file://"):
        return ""
    raw = href[len("file://") :]
    raw_lower = raw.lower()
    if raw_lower == "localhost" or raw_lower.startswith("localhost/"):
        raw = raw[len("localhost") :]
    if not raw.startswith("/"):
        return ""
    return decode_uri_component_safe(_PERCENT_RE.sub("%25", raw))


def _encode_uri_path_part(part: str) -> str:
    if not part:
        return ""
    safe = _PERCENT_RE.sub("%25", part)
    try:
        return quote(unquote(safe), safe="")
    except Exception:
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
    if uri.lower().split(":", 1)[0] in _UNSAFE_SCHEMES:
        return ""
    if uri.lower().startswith("file:"):
        return canonicalize_file_uri(uri)
    if _REMOTE_URI_RE.match(uri):
        return canonicalize_remote_uri(uri)
    return uri


def match_path(query: str) -> dict | None:
    if not is_path_query(query):
        return None
    resolved = expand_path(query)
    path = Path(resolved)
    if not path.exists():
        return {
            "path": resolved,
            "kind": "missing",
            "title": query.strip(),
            "description": "Path not found",
            "icon": "dialog-warning",
            "exists": False,
            "is_dir": False,
        }
    is_dir = path.is_dir()
    return {
        "path": str(path),
        "kind": "directory" if is_dir else "file",
        "title": collapse_home(str(path)),
        "description": "Open path",
        "icon": "folder" if is_dir else "text-x-generic",
        "exists": True,
        "is_dir": is_dir,
    }


def terminal_spec(find_in_path: Any | None = None) -> dict | None:
    if find_in_path is None:
        find_in_path = which
    if find_in_path("xdg-terminal-exec"):
        return {"argv": ["xdg-terminal-exec"], "use_directory_cwd": True}
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
    if find_in_path is None:
        find_in_path = which
    spec = terminal_spec(find_in_path)
    if not spec or not directory:
        return None
    if spec.get("use_directory_cwd"):
        return {"argv": list(spec["argv"]), "cwd": directory}
    flag = spec["working_directory_flag"]
    return {"argv": list(spec["argv"]) + [f"{flag}={directory}"], "cwd": None}


def terminal_row_meta(directory: str, home: str | None = None) -> dict:
    return {
        "title": "Open in Terminal",
        "description": collapse_home(directory, home),
        "icon": "utilities-terminal",
        "path": directory,
        "in_terminal": True,
    }


def first_terminal() -> str | None:
    for name in TERMINALS:
        found = which(name)
        if found:
            return found
    return None
