"""Thin QtDBus helpers replacing the Gio D-Bus surface the providers used.

Everything degrades to None/False when there is no bus or the peer is missing,
matching how the old code wrapped Gio calls in try/except - a provider must
never break search because a D-Bus service is absent.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage

logger = logging.getLogger(__name__)


def session_bus() -> QDBusConnection:
    return QDBusConnection.sessionBus()


def system_bus() -> QDBusConnection:
    return QDBusConnection.systemBus()


def call(
    bus: QDBusConnection,
    service: str,
    path: str,
    interface: str,
    method: str,
    args: list[Any] | None = None,
    timeout_ms: int = 2000,
) -> list[Any] | None:
    """Synchronous method call; returns the reply arguments, or None on any failure."""
    if not bus.isConnected():
        return None
    message = QDBusMessage.createMethodCall(service, path, interface, method)
    if args:
        message.setArguments(args)
    reply = bus.call(message, timeout=timeout_ms)
    if reply.type() != QDBusMessage.MessageType.ReplyMessage:
        return None
    return list(reply.arguments())


def get_property(
    bus: QDBusConnection, service: str, path: str, interface: str, prop: str, timeout_ms: int = 2000
) -> Any | None:
    reply = call(bus, service, path, "org.freedesktop.DBus.Properties", "Get", [interface, prop], timeout_ms)
    if not reply:
        return None
    value = reply[0]
    # Unwrap QDBusVariant / QDBusArgument wrappers
    inner = getattr(value, "variant", None)
    if callable(inner):
        return inner()
    return value


def unwrap(value: Any) -> Any:
    """Recursively unwrap QDBusVariant/QDBusArgument into plain Python values.

    Complex D-Bus types (nested structs, non-string-keyed maps) come back as
    QDBusArgument; where PySide6 cannot convert them this returns None and the
    caller's graceful-degradation path handles it.
    """
    variant = getattr(value, "variant", None)
    if callable(variant):
        return unwrap(variant())
    if type(value).__name__ == "QDBusArgument":
        as_variant = getattr(value, "asVariant", None)
        if callable(as_variant):
            try:
                return unwrap(as_variant())
            except Exception:  # noqa: BLE001
                return None
        return None
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    if isinstance(value, tuple):
        return tuple(unwrap(item) for item in value)
    if isinstance(value, dict):
        return {unwrap(k): unwrap(v) for k, v in value.items()}
    return value


def uint32(value: int) -> Any:
    """Explicitly-typed uint32 argument (QtDBus marshals plain ints as int32)."""
    from PySide6.QtCore import QMetaType
    from PySide6.QtDBus import QDBusArgument

    # pyrefly: ignore [no-matching-overload]
    return QDBusArgument(int(value), QMetaType.Type.UInt.value)


def name_has_owner(bus: QDBusConnection, name: str) -> bool:
    reply = call(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner", [name])
    return bool(reply and reply[0])


class SignalSubscription(QObject):
    """Holds a D-Bus signal connection; call .unsubscribe() to drop it."""

    def __init__(
        self,
        bus: QDBusConnection,
        service: str,
        path: str,
        interface: str,
        signal_name: str,
        callback: Callable[[list[Any]], None],
        message_callback: Callable[[QDBusMessage], None] | None = None,
    ) -> None:
        super().__init__()
        self._bus = bus
        self._args = (service, path, interface, signal_name)
        self._callback = callback
        self._message_callback = message_callback
        # The receiver+slot-signature overload dispatches the full QDBusMessage to us,
        # so one generic slot serves any signal signature.
        # pyrefly: ignore [bad-argument-type]
        self.connected = bus.connect(service, path, interface, signal_name, self, "handleDBusSignal(QDBusMessage)")

    @Slot(QDBusMessage)
    def handleDBusSignal(self, message: QDBusMessage) -> None:  # noqa: N802 - referenced by slot signature
        try:
            if self._message_callback is not None:
                self._message_callback(message)
            else:
                self._callback(list(message.arguments()))
        except Exception:
            logger.exception("Unhandled error in D-Bus signal handler for %s", self._args[3])

    def unsubscribe(self) -> None:
        if self.connected:
            # pyrefly: ignore [no-matching-overload]
            self._bus.disconnect(*self._args, self, "handleDBusSignal(QDBusMessage)")
            self.connected = False

    def signal_unsubscribe(self, _sub_id: int = 0) -> None:
        """Gio-style alias so watch lists holding (connection, id) pairs keep working."""
        self.unsubscribe()


def subscribe(
    bus: QDBusConnection,
    service: str,
    path: str,
    interface: str,
    signal_name: str,
    callback: Callable[[list[Any]], None],
) -> SignalSubscription | None:
    if not bus.isConnected():
        return None
    subscription = SignalSubscription(bus, service, path, interface, signal_name, callback)
    return subscription if subscription.connected else None
