from __future__ import annotations

import logging
import re
import shlex
from pathlib import Path

from ulauncher.modes.apps.try_raise_app import try_raise_app
from ulauncher.utils.desktop_app import DesktopApp, dbus_activate_application, find_terminal
from ulauncher.utils.launch_detached import launch_detached
from ulauncher.utils.settings import Settings

logger = logging.getLogger(__name__)


def _get_exec(app: DesktopApp, action_name: str | None = None) -> str | None:
    """Return the launch command for the app, or one of its actions, with field codes resolved."""
    desktop_entry_path = app.get_filename()
    exec_line = app._entry.get_action_exec(action_name) if action_name else app.get_commandline()  # noqa: SLF001
    if not exec_line:
        return None
    if desktop_entry_path:
        exec_line = exec_line.replace("%k", desktop_entry_path)
    # strip field codes %f, %F, %u, %U, etc
    return re.sub(r"\%[uUfFdDnNickvm]", "", exec_line).strip()


def _load_app(desktop_entry_name: str) -> DesktopApp | None:
    app = DesktopApp.new(desktop_entry_name)
    if not app:
        logger.error("Could not load app %s", desktop_entry_name)
    return app


def launch_app(desktop_entry_name: str, action_name: str | None = None, *, raise_existing: bool = True) -> bool:
    app_id = Path(desktop_entry_name).stem if desktop_entry_name.endswith(".desktop") else desktop_entry_name
    settings = Settings.load()
    app = _load_app(desktop_entry_name)
    if not app:
        return False

    is_dbus = app.get_boolean("DBusActivatable")
    is_terminal = app.get_boolean("Terminal")
    use_custom_terminal = is_terminal and bool(settings.terminal_command)
    app_exec = _get_exec(app, action_name)

    if action_name is not None and (is_dbus or not app_exec or (is_terminal and not use_custom_terminal)):
        # for actions with no command of our own to spawn, let the app handle its action
        # (D-Bus activation for DBusActivatable entries, the action's own Exec otherwise)
        return app.launch_action(action_name)
    if raise_existing and action_name is None and (settings.raise_if_started or app.get_boolean("SingleMainWindow")):
        app_wm_id = (app.get_string("StartupWMClass") or (Path(app_exec).name if app_exec else app_id)).lower()
        if try_raise_app(app_wm_id):
            return True

    if is_dbus:  # an action with DBus activation already returned above
        # https://specifications.freedesktop.org/desktop-entry-spec/latest/dbus.html
        entry_id = app.get_id() or f"{app_id}.desktop"
        if dbus_activate_application(entry_id):
            logger.info("Activated application %s over D-Bus", entry_id)
            return True
        logger.error("Could not activate app %s over D-Bus", app_id)
        return False
    if is_terminal and not use_custom_terminal:
        if not app_exec:
            logger.error("Could not get Exec for terminal app %s", app_id)
            return False
        terminal = find_terminal()
        if terminal is None:
            logger.error("No terminal emulator found to launch %s", app_id)
            return False
        try:
            cmd = [terminal[0], terminal[1], *shlex.split(app_exec)]
        except ValueError:
            logger.exception("Could not parse command for app %s: %r", app_id, app_exec)
            return False
    elif app_exec:
        shell_string = settings.terminal_command if use_custom_terminal else app_exec
        try:
            cmd = shlex.split(shell_string)
            if use_custom_terminal:
                cmd = [*cmd, app_exec]
        except ValueError:
            logger.exception("Could not parse command for app %s: %r", app_id, shell_string)
            return False
    else:
        logger.error("Could not get Exec for app %s", app_id)
        return False

    logger.info("Run %s (%s) Exec %s", f"action {action_name}" if action_name else "application", app_id, cmd)
    launch_detached(cmd, app.get_string("Path"))
    return True
