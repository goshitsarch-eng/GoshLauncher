from __future__ import annotations

from ulauncher import app_id
from ulauncher.cli import CLIArguments


def run(_: CLIArguments) -> int:
    from ulauncher.cli.commands.show import call_app
    from ulauncher.utils.dbus import check_app_running

    if check_app_running(app_id):
        return 0 if call_app("ToggleWindow") else 1
    # Not running: toggling from nothing means show
    return 0 if call_app("ShowWindow") else 1
