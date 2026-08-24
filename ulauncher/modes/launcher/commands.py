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


def resolve_command(query: str) -> list[str] | None:
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
        first = str(Path(first).expanduser())
        argv[0] = first
    elif "/" in first and not first.startswith("/"):
        argv[0] = str(Path.home() / first)
        first = argv[0]
    found = which(argv[0], path=extra_path())
    if found:
        argv[0] = found
        return argv
    if Path(argv[0]).is_file() and os.access(argv[0], os.X_OK):
        return argv
    return None
