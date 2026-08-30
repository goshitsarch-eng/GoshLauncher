"""Desktop notifications over the org.freedesktop.Notifications D-Bus interface."""

from __future__ import annotations

import logging

from ulauncher import app_display_name, app_id

logger = logging.getLogger(__name__)

_URGENCY_CRITICAL = 2


def show_notification(title: str, body: str, icon: str = app_id) -> None:
    from PySide6.QtDBus import QDBusConnection, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        logger.warning("No session bus; cannot show notification: %s", title)
        return
    message = QDBusMessage.createMethodCall(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "Notify",
    )
    message.setArguments([app_display_name, 0, icon, title, body, [], {"urgency": _URGENCY_CRITICAL}, -1])
    reply = bus.call(message)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        logger.warning("Notification failed: %s", reply.errorMessage())
