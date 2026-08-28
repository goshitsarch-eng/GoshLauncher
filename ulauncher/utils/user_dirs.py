"""XDG user directories (~/.config/user-dirs.dirs), replacing GLib.get_user_special_dir."""

from __future__ import annotations

import os
import re

from ulauncher import paths

_LINE = re.compile(r'^\s*XDG_([A-Z]+)_DIR\s*=\s*"(.*)"\s*$')

# Spec defaults used when user-dirs.dirs is missing or lacks an entry
_DEFAULTS = {
    "DESKTOP": "Desktop",
    "DOWNLOAD": "Downloads",
    "TEMPLATES": "Templates",
    "PUBLICSHARE": "Public",
    "DOCUMENTS": "Documents",
    "MUSIC": "Music",
    "PICTURES": "Pictures",
    "VIDEOS": "Videos",
}


def _load() -> dict[str, str]:
    dirs: dict[str, str] = {}
    try:
        with open(os.path.join(paths.XDG_CONFIG_HOME, "user-dirs.dirs"), encoding="utf-8") as f:
            for line in f:
                match = _LINE.match(line)
                if not match:
                    continue
                name, value = match.groups()
                value = value.replace("$HOME", paths.HOME)
                if value.startswith("/"):
                    dirs[name] = os.path.normpath(value)
    except OSError:
        pass
    return dirs


_user_dirs = _load()


def get_user_dir(name: str) -> str | None:
    """Path for an XDG user dir name (e.g. "DOWNLOAD", "DOCUMENTS"), or None when it
    is disabled (set to $HOME per the spec's convention for "no such dir")."""
    configured = _user_dirs.get(name)
    if configured:
        return None if configured == paths.HOME else configured
    default = _DEFAULTS.get(name)
    return os.path.join(paths.HOME, default) if default else None
