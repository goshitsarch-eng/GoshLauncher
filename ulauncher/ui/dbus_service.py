"""The app's session D-Bus service: single-instance ownership and the control interface.

Owning the well-known name doubles as the single-instance lock (as it did under
GApplication). The exported object answers the CLI's method calls; TriggerEvent
tunnels arbitrary EventBus events (used by extension install/preview commands).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot
from PySide6.QtDBus import QDBusConnection

import ulauncher
from ulauncher.utils.eventbus import EventBus

if TYPE_CHECKING:
    from ulauncher.ui.app import UlauncherApp

logger = logging.getLogger(__name__)
events = EventBus()


class DBusService(QObject):
    """Exported at /com/goshapps/GoshLauncher with every public slot callable over D-Bus."""

    def __init__(self, app: UlauncherApp) -> None:
        super().__init__()
        self._app = app

    @Slot()
    def ShowWindow(self) -> None:
        self._app.show_launcher()

    @Slot()
    def HideWindow(self) -> None:
        self._app.close_launcher()

    @Slot()
    def ToggleWindow(self) -> None:
        self._app.toggle_window()

    @Slot()
    def ShowPreferences(self) -> None:
        self._app.show_preferences()

    @Slot(str)
    def SetQuery(self, query: str) -> None:
        self._app.activate_query(query)

    @Slot(bool)
    def ToggleTrayIcon(self, enable: bool) -> None:
        self._app.toggle_tray_icon(enable)

    @Slot(str)
    def TriggerEvent(self, json_message: str) -> None:
        """Parses and delegates custom JSON messages to the EventBus listener (if any)"""
        try:
            if (data := json.loads(json_message)) and isinstance(data, dict):
                name = data.get("name")
                args = data.get("args")
                if isinstance(name, str) and isinstance(args, list):
                    events.emit(name, *args)
                    return
            logger.error("Custom message fields 'name' or 'args' are missing or invalid: %s", json_message)
        except json.JSONDecodeError:
            logger.exception("Failed to parse custom message as JSON: %s", json_message)


def register(app: UlauncherApp) -> DBusService | None:
    """Claim the app's bus name and export the control object.

    Returns None when another instance already owns the name (or there is no bus),
    in which case this process should defer to it.
    """
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        logger.warning("No session D-Bus; single-instance detection and the CLI control channel are off")
        return DBusService(app)  # still constructed so in-process calls work
    if not bus.registerService(ulauncher.app_id):
        return None
    service = DBusService(app)
    bus.registerObject(ulauncher.dbus_path, service, QDBusConnection.RegisterOption.ExportAllSlots)
    return service


def call_running_instance(method: str, *args: object) -> bool:
    """Invoke a method on the already-running instance. Returns False when unreachable."""
    from PySide6.QtDBus import QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    message = QDBusMessage.createMethodCall(ulauncher.app_id, ulauncher.dbus_path, "", method)
    message.setArguments(list(args))
    reply = bus.call(message)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        logger.warning("D-Bus call %s failed: %s", method, reply.errorMessage())
        return False
    return True
