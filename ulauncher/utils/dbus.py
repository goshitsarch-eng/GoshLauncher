"""Session-bus helpers built on QtDBus.

The app process registers the ``com.goshapps.GoshLauncher`` service and exposes a
``TriggerEvent`` method (see ``ulauncher.ui.dbus_service``); short-lived CLI
processes use these helpers to check whether the app runs and to deliver
EventBus events into it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import ulauncher

logger = logging.getLogger(__name__)


def _session_bus() -> Any:
    """The QtDBus session bus.

    Deliberately does NOT create a QCoreApplication: synchronous calls work without
    one, and creating a QCoreApplication here would block the real QApplication from
    being constructed later in the app process (v5_killer runs before it exists).
    """
    from PySide6.QtDBus import QDBusConnection

    return QDBusConnection.sessionBus()


def check_app_running(app_id: str) -> bool:
    """Check if app is running by checking if the D-Bus service name is owned."""
    bus = _session_bus()
    if not bus.isConnected():
        return False
    reply = bus.interface().isServiceRegistered(app_id)
    return bool(reply.isValid() and reply.value())


def get_app_pid(app_id: str) -> int | None:
    """Get the PID of a D-Bus app"""
    bus = _session_bus()
    if not bus.isConnected() or not check_app_running(app_id):
        return None
    reply = bus.interface().servicePid(app_id)
    if not reply.isValid():
        return None
    return int(reply.value())


def dbus_trigger_event(name: str, *args: Any) -> None:
    """Sends a D-Bus message to the app, which is delegated to the EventBus listener matching the name."""
    from PySide6.QtDBus import QDBusMessage

    bus = _session_bus()
    if not check_app_running(ulauncher.app_id):
        logger.debug("App is not running, skipping D-Bus trigger event: %s", name)
        return

    json_message = json.dumps({"name": name, "args": list(args)})
    # Empty interface name matches the method on whatever interface the app exported it under.
    message = QDBusMessage.createMethodCall(ulauncher.app_id, ulauncher.dbus_path, "", "TriggerEvent")
    message.setArguments([json_message])
    # Synchronous call so the message reaches the bus before a short-lived CLI process exits.
    reply = bus.call(message)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        logger.warning("DBus call failed: %s", reply.errorMessage())
