"""Spawn and URI launch, from goshos gioLaunch.js."""

from __future__ import annotations

import os
from shutil import which
from typing import Any, Callable

from ulauncher.modes.launcher.commands import (
    command_uses_path_lookup,
    extra_path_dirs,
    find_user_program,
    first_command_arg,
    join_path_dirs,
)

_program_path_cache: dict[str, str | None] = {}
_launch_contexts: set[Any] = set()


def reset_program_path_cache() -> None:
    _program_path_cache.clear()


def find_in_user_path(name: str) -> str | None:
    if name in _program_path_cache:
        return _program_path_cache[name]
    home = os.path.expanduser("~")
    found = find_user_program(
        name,
        which,
        lambda path: os.access(path, os.X_OK),
        extra_path_dirs(home),
    )
    _program_path_cache[name] = found
    return found


def spawn_argv(
    argv: list[str],
    cwd: str | None = None,
    spawn: Callable[..., Any] | None = None,
) -> None:
    from ulauncher.modes.launcher.paths import resolve_command_argv

    home = os.path.expanduser("~")
    resolved = resolve_command_argv(list(argv), home)
    exe = first_command_arg(resolved)
    if command_uses_path_lookup(exe):
        found = find_in_user_path(exe)
        if not found:
            return
        resolved[0] = found

    workdir = cwd or home
    path = join_path_dirs(extra_path_dirs(home), os.environ.get("PATH") or "")
    extra_env = {"PATH": path} if path else None
    if spawn is None:
        from ulauncher.utils.launch_detached import launch_detached

        spawn = launch_detached
    try:
        spawn(resolved, working_dir=workdir, extra_env=extra_env)
    except Exception:
        return


def open_uri(uri: str, opener: Callable[[str], Any] | None = None) -> None:
    if not uri:
        return
    from ulauncher.modes.launcher.paths import canonicalize_launch_uri
    from ulauncher.modes.launcher.urls import is_unsafe_launch_uri

    if is_unsafe_launch_uri(uri):
        return
    launch = canonicalize_launch_uri(uri)
    if not launch:
        return
    if opener is not None:
        opener(launch)
        return
    # open_detached resolves the URI's registered handler itself (remote filesystem
    # schemes fall back to the default file manager, which mounts the share).
    from ulauncher.utils.launch_detached import open_detached

    open_detached(launch)
