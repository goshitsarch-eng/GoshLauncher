from __future__ import annotations

import logging
import os
import subprocess
import sys

from ulauncher.utils.systemd_controller import SystemdController

logger = logging.getLogger(__name__)


def launch_detached(
    cmd: list[str],
    working_dir: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> None:
    use_systemd_run = SystemdController("ulauncher").status().is_active
    if use_systemd_run:
        cmd = ["systemd-run", "--user", "--scope", *cmd]

    env = dict(os.environ.items())
    if extra_env:
        env.update(extra_env)
    # Don't leak a platform override we may run under into launched apps -
    # they should pick their own backend on the user's session.
    for var in ("QT_QPA_PLATFORM", "GDK_BACKEND"):
        if env.get(var) not in (None, "wayland"):
            env.pop(var, None)

    # start_new_session=True runs setsid in the child, so the launched app is definitely
    # detached from the launcher process and survives it exiting or being Ctrl-C'd.
    # Detach stdio from a controlling terminal for the same reason (like nohup, but to
    # /dev/null instead of a file).
    stdio = subprocess.DEVNULL if sys.stdout.isatty() else None
    try:
        subprocess.Popen(
            cmd,
            cwd=working_dir or None,
            env=env,
            start_new_session=not use_systemd_run,
            stdin=stdio,
            stdout=stdio,
            stderr=stdio,
            close_fds=True,
        )
    except OSError:
        logger.exception('Could not launch "%s"', cmd)


def open_detached(path_or_url: str) -> None:
    """Open a path or URI with its registered handler.

    Non-file URIs are resolved through the mime-apps database ourselves instead of
    trusting xdg-open: network shares (smb://, sftp://, ...) fall back to the default
    file manager, which mounts the share itself, where xdg-open would fail or demand
    "another app" when no x-scheme-handler is registered.
    """
    scheme = path_or_url.split(":", 1)[0].lower() if ":" in path_or_url else ""
    if scheme and not path_or_url.startswith("/") and scheme != "file":
        from ulauncher.utils.mime_apps import handler_for_uri

        handler = handler_for_uri(path_or_url)
        if handler is not None and handler.launch_uris([path_or_url]):
            return
    launch_detached(["xdg-open", path_or_url])
