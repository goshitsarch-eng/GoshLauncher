"""Prefix-only argv command runner (not a shell)."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from shutil import which
from typing import Callable

# goshos userPath.js: user dirs first, then the system Flatpak export dir
EXTRA_PATH_DIRS = (
    Path.home() / ".local" / "bin",
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin",
    Path.home() / ".cargo" / "bin",
    Path.home() / "go" / "bin",
    Path.home() / "bin",
    Path("/var/lib/flatpak/exports/bin"),
)


def extra_path_dirs(home: str | None = None) -> list[str]:
    dirs: list[str] = []
    if home:
        dirs.extend(
            [
                f"{home}/.local/bin",
                f"{home}/.local/share/flatpak/exports/bin",
                f"{home}/.cargo/bin",
                f"{home}/go/bin",
                f"{home}/bin",
            ]
        )
    dirs.append("/var/lib/flatpak/exports/bin")
    return dirs


def join_path_dirs(extra_dirs: list[str], current_path: str | None) -> str:
    parts = list(extra_dirs)
    if current_path:
        parts.append(current_path)
    return os.pathsep.join(parts)


def extra_path() -> str:
    parts = [path for path in extra_path_dirs(str(Path.home())) if Path(path).is_dir()]
    current = os.environ.get("PATH", "")
    return join_path_dirs(parts, current)


def find_user_program(
    name: str,
    find_in_path: Callable[[str], str | None],
    path_exists: Callable[[str], bool],
    extra_dirs: list[str],
) -> str | None:
    if not name:
        return None
    found = find_in_path(name)
    if found:
        return found
    for directory in extra_dirs:
        candidate = f"{directory}/{name}"
        if path_exists(candidate):
            return candidate
    return None


def first_command_arg(argv: list[str] | None) -> str:
    if not argv:
        return ""
    exe = argv[0]
    return exe if isinstance(exe, str) else ""


def command_uses_path_lookup(exe: str) -> bool:
    return bool(exe) and "/" not in exe


def command_file_is_ready(is_directory: bool, is_executable: bool) -> bool:
    return (not is_directory) and bool(is_executable)


def command_is_ready(
    exe: str,
    find_in_path: Callable[[str], str | None],
    path_exists: Callable[[str], bool],
) -> bool:
    if not exe:
        return False
    if command_uses_path_lookup(exe):
        return bool(find_in_path(exe))
    return bool(path_exists(exe))


def command_row_meta(query: str, ready: bool, checking: bool = False) -> dict:
    if checking:
        return {
            "type": "command",
            "title": query,
            "description": "Checking command",
            "icon": "utilities-terminal-symbolic",
            "id": f"command:{query}",
            "activatable": False,
            "ready": False,
            "checking": True,
        }
    if not ready:
        return {
            "type": "command",
            "title": query,
            "description": "Command not found",
            "icon": "dialog-warning-symbolic",
            "id": f"command:{query}",
            "activatable": False,
            "ready": False,
            "checking": False,
        }
    return {
        "type": "command",
        "title": query,
        "description": "Run command",
        "icon": "utilities-terminal-symbolic",
        "id": f"command:{query}",
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
    from ulauncher.modes.launcher.paths import resolve_command_argv

    return resolve_command_argv(argv)


def resolve_command_row(query: str) -> dict | None:
    argv = parse_command_argv(query)
    if not argv:
        return None
    exe = first_command_arg(argv)
    path_env = extra_path()

    def find_in_path(name: str) -> str | None:
        from ulauncher.utils.host import find_program, is_flatpak

        return find_program(name) if is_flatpak() else which(name, path=path_env)

    ready = command_is_ready(exe, find_in_path, os.path.exists)
    if command_uses_path_lookup(exe):
        found = find_in_path(exe)
        if found:
            argv[0] = found
    elif ready:
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
    # Deferred to the next main-loop turn to keep the callback contract async
    # (callers arm their lookup state before the result may arrive).
    from ulauncher.utils import scheduling

    scheduling.run_when_idle(lambda: on_ready(_command_file_ready(exe)))


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
