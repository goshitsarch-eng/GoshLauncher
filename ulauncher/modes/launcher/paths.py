"""Open ~/ ./ and absolute filesystem paths."""

from __future__ import annotations

import os
from pathlib import Path

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
    "blackbox",
)


def expand_path(query: str) -> str:
    text = query.strip()
    if text == "~" or text.startswith("~/"):
        return str(Path(text).expanduser())
    if text in (".", "./") or text.startswith("./"):
        home = Path.home()
        rest = text[2:] if text.startswith("./") else ""
        return str(home / rest) if rest else str(home)
    if text == ".." or text.startswith("../"):
        return str((Path.home() / text).resolve())
    return text


def collapse_home(path: str) -> str:
    home = str(Path.home())
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + path[len(home) :]
    return path


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
        "description": "Open folder" if is_dir else "Open file",
        "icon": "folder" if is_dir else "text-x-generic",
        "exists": True,
        "is_dir": is_dir,
    }


def first_terminal() -> str | None:
    from shutil import which

    for name in TERMINALS:
        found = which(name)
        if found:
            return found
    return None
