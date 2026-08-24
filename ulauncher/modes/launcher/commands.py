"""Prefix-only argv command runner (not a shell)."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from shutil import which

EXTRA_PATH_DIRS = (
    Path.home() / ".local" / "bin",
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin",
    Path("/var/lib/flatpak/exports/bin"),
    Path.home() / ".cargo" / "bin",
    Path.home() / "go" / "bin",
    Path.home() / "bin",
)


def extra_path() -> str:
    parts = [str(p) for p in EXTRA_PATH_DIRS if p.is_dir()]
    current = os.environ.get("PATH", "")
    return os.pathsep.join([*parts, current]) if parts else current


def first_command_arg(argv: list[str] | None) -> str:
    if not argv:
        return ""
    exe = argv[0]
    return exe if isinstance(exe, str) else ""


def command_uses_path_lookup(exe: str) -> bool:
    return bool(exe) and "/" not in exe


def command_file_is_ready(is_directory: bool, is_executable: bool) -> bool:
    return (not is_directory) and bool(is_executable)


def command_row_meta(query: str, ready: bool, checking: bool = False) -> dict:
    if checking:
        return {
            "title": query,
            "description": "Checking command",
            "icon": "utilities-terminal",
            "ready": False,
            "checking": True,
        }
    if not ready:
        return {
            "title": query,
            "description": "Command not found",
            "icon": "dialog-warning",
            "ready": False,
            "checking": False,
        }
    return {
        "title": query,
        "description": "Run command",
        "icon": "utilities-terminal",
        "ready": True,
        "checking": False,
    }


def parse_command_argv(query: str) -> list[str] | None:
    text = query.strip()
    if not text:
        return None
    try:
        argv = shlex.split(text, posix=True)
    except ValueError:
        return None
    if not argv:
        return None
    first = argv[0]
    if first.startswith("~"):
        argv[0] = str(Path(first).expanduser())
    elif "/" in first and not first.startswith("/"):
        argv[0] = str(Path.home() / first)
    return argv


def resolve_command_row(query: str) -> dict | None:
    argv = parse_command_argv(query)
    if not argv:
        return None
    exe = first_command_arg(argv)
    ready = False
    if command_uses_path_lookup(exe):
        found = which(exe, path=extra_path())
        if found:
            argv[0] = found
            ready = True
    else:
        path = Path(exe)
        ready = command_file_is_ready(path.is_dir(), path.is_file() and os.access(exe, os.X_OK))
    meta = command_row_meta(query.strip(), ready)
    meta["argv"] = argv if ready else []
    return meta


def resolve_command(query: str) -> list[str] | None:
    row = resolve_command_row(query)
    if not row or not row.get("ready"):
        return None
    argv = row.get("argv")
    return list(argv) if argv else None
