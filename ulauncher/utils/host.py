"""Host application access for the Flatpak launcher package."""

from __future__ import annotations

import os
from shutil import which


def is_flatpak() -> bool:
    return os.environ.get("FLATPAK_ID") == "com.goshapps.GoshLauncher"


def find_program(name: str) -> str | None:
    if not is_flatpak():
        return which(name)
    candidates = (
        [name]
        if os.path.isabs(name)
        else [os.path.expanduser(f"~/.local/bin/{name}"), f"/usr/local/bin/{name}", f"/usr/bin/{name}", f"/bin/{name}"]
    )
    for path in candidates:
        visible_path = f"/run/host{path}" if path.startswith(("/usr/", "/bin/")) else path
        if os.path.isfile(visible_path) and os.access(visible_path, os.X_OK):
            return path
    return None


def host_argv(argv: list[str], working_dir: str | None = None) -> list[str]:
    if not is_flatpak():
        return argv
    prefix = ["flatpak-spawn", "--host"]
    if working_dir:
        prefix.append(f"--directory={working_dir}")
    # Desktop-entry %k expands to a sandbox-visible host path.
    return [*prefix, *[arg.removeprefix("/run/host") if arg.startswith("/run/host/") else arg for arg in argv]]
