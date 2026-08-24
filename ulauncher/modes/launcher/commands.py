"""Prefix-only argv command runner (not a shell)."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from shutil import which
from typing import Any, Callable

# goshos userPath.js: user dirs first, then the system Flatpak export dir
EXTRA_PATH_DIRS = (
    Path.home() / ".local" / "bin",
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin",
    Path.home() / ".cargo" / "bin",
    Path.home() / "go" / "bin",
    Path.home() / "bin",
    Path("/var/lib/flatpak/exports/bin"),
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
            "icon": "utilities-terminal-symbolic",
            "ready": False,
            "checking": True,
        }
    if not ready:
        return {
            "title": query,
            "description": "Command not found",
            "icon": "dialog-warning-symbolic",
            "ready": False,
            "checking": False,
        }
    return {
        "title": query,
        "description": "Run command",
        "icon": "utilities-terminal-symbolic",
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
    home = Path.home()
    expanded: list[str] = []
    for index, arg in enumerate(argv):
        if arg.startswith("~"):
            expanded.append(str(Path(arg).expanduser()))
        elif arg in {".", ".."} or arg.startswith("./") or arg.startswith("../"):
            expanded.append(str((home / arg).resolve()) if arg != "." else str(home))
        elif index == 0 and "/" in arg and not arg.startswith("/"):
            expanded.append(str(home / arg))
        else:
            expanded.append(arg)
    return expanded


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
    meta["cwd"] = str(Path.home())
    return meta


def resolve_command(query: str) -> list[str] | None:
    row = resolve_command_row(query)
    if not row or not row.get("ready"):
        return None
    argv = row.get("argv")
    return list(argv) if argv else None


class _CommandLookup:
    query = ""
    row: dict | None = None
    resolved = False
    on_ready: Callable[[], None] | None = None
    load_id = 0
    pending_finish: Callable[[], None] | None = None


_command_lookup = _CommandLookup()


def command_needs_async(query: str) -> bool:
    argv = parse_command_argv(query)
    if not argv:
        return False
    return not command_uses_path_lookup(first_command_arg(argv))


def command_is_resolved(query: str) -> bool:
    return _command_lookup.query == query and _command_lookup.resolved


def _command_file_ready(exe: str) -> bool:
    path = Path(exe)
    return command_file_is_ready(path.is_dir(), path.is_file() and os.access(exe, os.X_OK))


def _apply_command_ready(query: str, argv: list[str], ready: bool, load_id: int) -> None:
    if load_id != _command_lookup.load_id:
        return
    if _command_lookup.resolved and _command_lookup.query == query:
        return
    meta = command_row_meta(query.strip(), ready)
    meta["argv"] = argv if ready else []
    meta["cwd"] = str(Path.home())
    _command_lookup.row = meta
    _command_lookup.resolved = True
    _command_lookup.pending_finish = None
    callback = _command_lookup.on_ready
    _command_lookup.on_ready = None
    if callback:
        callback()


def _start_command_stat(exe: str, on_ready: Callable[[bool], None]) -> None:
    try:
        from ulauncher.gi import Gio, GLib
    except Exception:
        on_ready(_command_file_ready(exe))
        return

    def _done(source: Any, result: Any) -> None:
        ready = False
        try:
            info = source.query_info_finish(result)
            ready = command_file_is_ready(
                info.get_file_type() == Gio.FileType.DIRECTORY,
                info.get_attribute_boolean("access::can-execute"),
            )
        except Exception:
            ready = False
        on_ready(ready)

    try:
        Gio.File.new_for_path(exe).query_info_async(
            "standard::type,access::can-execute",
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_DEFAULT,
            None,
            _done,
        )
    except Exception:
        on_ready(_command_file_ready(exe))


def invalidate_command_lookup() -> None:
    _command_lookup.query = ""
    _command_lookup.row = None
    _command_lookup.resolved = False
    _command_lookup.on_ready = None
    _command_lookup.pending_finish = None
    _command_lookup.load_id += 1


def search_command(query: str) -> list[dict]:
    argv = parse_command_argv(query)
    if not argv:
        return []
    exe = first_command_arg(argv)
    if command_uses_path_lookup(exe):
        row = resolve_command_row(query)
        return [row] if row else []
    if _command_lookup.query == query and _command_lookup.resolved and _command_lookup.row is not None:
        return [_command_lookup.row]
    meta = command_row_meta(query.strip(), ready=False, checking=True)
    meta["argv"] = []
    meta["cwd"] = str(Path.home())
    return [meta]


def ensure_command(query: str, on_ready: Callable[[], None]) -> None:
    argv = parse_command_argv(query)
    if not argv:
        return
    if command_uses_path_lookup(first_command_arg(argv)):
        return
    if _command_lookup.query == query and _command_lookup.resolved:
        return
    _command_lookup.on_ready = on_ready
    if _command_lookup.query == query and not _command_lookup.resolved:
        return
    _command_lookup.load_id += 1
    load_id = _command_lookup.load_id
    _command_lookup.query = query
    _command_lookup.resolved = False
    resolved = list(argv)
    exe = first_command_arg(resolved)

    def finish_sync() -> None:
        _apply_command_ready(query, resolved, _command_file_ready(exe), load_id)

    _command_lookup.pending_finish = finish_sync
    _start_command_stat(exe, lambda ready: _apply_command_ready(query, resolved, ready, load_id))


def flush_command_lookup() -> None:
    finish = _command_lookup.pending_finish
    _command_lookup.pending_finish = None
    if finish:
        finish()
