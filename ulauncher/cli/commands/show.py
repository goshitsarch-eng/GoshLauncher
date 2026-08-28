from __future__ import annotations

import sys
import time

from ulauncher import app_id
from ulauncher.cli import CLIArguments

_START_WAIT_SEC = 8.0
_POLL_SEC = 0.1


def call_app(method: str, *args: object) -> bool:
    """Invoke a method on the running app over D-Bus, starting it when needed.

    A D-Bus-activatable install starts implicitly through the method call; the
    explicit spawn covers running from a source checkout without the service file.
    """
    from ulauncher.ui.dbus_service import call_running_instance
    from ulauncher.utils.dbus import check_app_running

    if call_running_instance(method, *args):
        return True

    from ulauncher.utils.launch_detached import launch_detached

    launch_detached([sys.argv[0] if sys.argv[0].endswith("ulauncher") else "ulauncher", "start"])
    deadline = time.monotonic() + _START_WAIT_SEC
    while time.monotonic() < deadline:
        if check_app_running(app_id):
            return call_running_instance(method, *args)
        time.sleep(_POLL_SEC)
    return False


def run(cli_args: CLIArguments) -> int:
    if cli_args.query is not None:
        return 0 if call_app("SetQuery", cli_args.query) else 1
    return 0 if call_app("ShowWindow") else 1
