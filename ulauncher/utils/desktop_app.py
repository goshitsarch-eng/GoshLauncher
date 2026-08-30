"""Gio.DesktopAppInfo replacement built on ulauncher.utils.desktop_entry.

Implements the exact method surface the app code used from the old PyGObject
wrapper (get_display_name, get_show_in, list_actions, launch_uris, ...), so
the apps mode and "open with" keep working without a GObject dependency.
Launching goes through subprocess (via launch_detached) or freedesktop D-Bus
activation for DBusActivatable entries.
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
from typing import Any

from ulauncher.utils.desktop_entry import DesktopEntry, find_desktop_entry, get_all_desktop_entries

logger = logging.getLogger(__name__)

_FIELD_CODE = re.compile(r"%[uUfFdDnNickvm]")

# Terminals to try for Terminal=true entries when no custom terminal command is
# configured, with the argument that precedes the command line.
_KNOWN_TERMINALS = [
    ("x-terminal-emulator", "-e"),
    ("konsole", "-e"),
    ("foot", "-e"),
    ("alacritty", "-e"),
    ("kitty", "-e"),
    ("wezterm", "start"),
    ("gnome-terminal", "--"),
    ("xfce4-terminal", "-x"),
    ("xterm", "-e"),
]


def find_terminal() -> tuple[str, str] | None:
    for terminal, exec_arg in _KNOWN_TERMINALS:
        if shutil.which(terminal):
            return terminal, exec_arg
    return None


def dbus_activate_application(desktop_id: str, action: str | None = None, uris: list[str] | None = None) -> bool:
    """Launch a DBusActivatable app via the org.freedesktop.Application interface."""
    from PySide6.QtDBus import QDBusConnection, QDBusMessage

    service = desktop_id[: -len(".desktop")] if desktop_id.endswith(".desktop") else desktop_id
    object_path = "/" + service.replace(".", "/").replace("-", "_")
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False

    platform_data: dict[str, Any] = {}
    if action is not None:
        message = QDBusMessage.createMethodCall(service, object_path, "org.freedesktop.Application", "ActivateAction")
        message.setArguments([action, [], platform_data])
    elif uris:
        message = QDBusMessage.createMethodCall(service, object_path, "org.freedesktop.Application", "Open")
        message.setArguments([uris, platform_data])
    else:
        message = QDBusMessage.createMethodCall(service, object_path, "org.freedesktop.Application", "Activate")
        message.setArguments([platform_data])
    reply = bus.call(message)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        logger.warning("D-Bus activation of %s failed: %s", service, reply.errorMessage())
        return False
    return True


def expand_exec(exec_line: str, desktop_file: str | None = None, uris: list[str] | None = None) -> list[str] | None:
    """Turn an Exec= line into argv, resolving field codes per the desktop entry spec.

    %f/%F get local paths, %u/%U get the URIs as given; the deprecated codes and
    %i/%c are dropped. Returns None for an unparsable line.
    """
    if desktop_file:
        exec_line = exec_line.replace("%k", shlex.quote(desktop_file))
    try:
        argv = shlex.split(exec_line)
    except ValueError:
        return None

    uris = uris or []
    paths = [uri[len("file://") :] if uri.startswith("file://") else uri for uri in uris]
    expanded: list[str] = []
    for arg in argv:
        if arg in ("%u", "%f"):
            if uris:
                expanded.append(paths[0] if arg == "%f" else uris[0])
        elif arg in ("%U", "%F"):
            expanded.extend(paths if arg == "%F" else uris)
        elif _FIELD_CODE.fullmatch(arg):
            continue
        else:
            expanded.append(_FIELD_CODE.sub("", arg))
    return expanded or None


class DesktopApp:
    """Desktop application entry with the old Gio.DesktopAppInfo method names."""

    def __init__(self, entry: DesktopEntry) -> None:
        self._entry = entry

    @staticmethod
    def new(app_id: str) -> DesktopApp | None:
        entry = find_desktop_entry(app_id)
        return DesktopApp(entry) if entry else None

    @staticmethod
    def new_from_filename(filename: str) -> DesktopApp | None:
        entry = DesktopEntry.from_file(filename)
        return DesktopApp(entry) if entry else None

    @staticmethod
    def get_all() -> list[DesktopApp]:
        return [DesktopApp(entry) for entry in get_all_desktop_entries()]

    def get_id(self) -> str | None:
        return self._entry.id

    def get_name(self) -> str:
        return self._entry.name

    def get_display_name(self) -> str:
        # Gio prefers X-GNOME-FullName ("Files" -> "GNOME Files") when present
        return self._entry.get_localized("X-GNOME-FullName") or self._entry.name

    def get_description(self) -> str | None:
        return self._entry.comment or None

    def get_generic_name(self) -> str | None:
        return self._entry.generic_name or None

    def get_keywords(self) -> list[str]:
        return self._entry.keywords

    def get_commandline(self) -> str | None:
        return self._entry.exec_line or None

    def get_executable(self) -> str:
        return self._entry.executable

    def get_filename(self) -> str | None:
        return self._entry.filename

    def get_string(self, key: str) -> str | None:
        return self._entry.get_string(key) or None

    def get_boolean(self, key: str) -> bool:
        return self._entry.get_boolean(key)

    def get_show_in(self) -> bool:
        return self._entry.show_in_current_desktop()

    def get_nodisplay(self) -> bool:
        return self._entry.no_display

    def list_actions(self) -> list[str]:
        return list(self._entry.get_actions())

    def get_action_name(self, action_name: str) -> str:
        return self._entry.get_actions().get(action_name, {}).get("name", "")

    def launch_action(self, action_name: str) -> bool:
        if self._entry.dbus_activatable and dbus_activate_application(self._entry.id, action=action_name):
            return True
        exec_line = self._entry.get_action_exec(action_name)
        if not exec_line:
            return False
        return self._spawn(exec_line)

    def launch_uris(self, uris: list[str] | None = None) -> bool:
        if self._entry.dbus_activatable and dbus_activate_application(self._entry.id, uris=uris):
            return True
        exec_line = self._entry.exec_line
        if not exec_line:
            return False
        return self._spawn(exec_line, uris)

    def _spawn(self, exec_line: str, uris: list[str] | None = None) -> bool:
        from ulauncher.utils.launch_detached import launch_detached

        argv = expand_exec(exec_line, self._entry.filename, uris)
        if not argv:
            logger.error("Could not parse Exec for app %s: %r", self._entry.id, exec_line)
            return False
        if self._entry.terminal:
            terminal = find_terminal()
            if terminal is None:
                logger.error("No terminal emulator found to launch %s", self._entry.id)
                return False
            argv = [terminal[0], terminal[1], *argv]
        launch_detached(argv, self._entry.working_dir or None)
        return True
