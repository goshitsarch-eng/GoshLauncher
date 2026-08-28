"""xdg-desktop-portal GlobalShortcuts for Ctrl+Space outside GNOME/XFCE/Plasma.

GNOME Shell extensions grab accelerators in-process. A GTK app cannot. GNOME,
XFCE, and Plasma persist a custom keybinding that launches the app. Other
Wayland sessions (Hyprland, Sway, niri, COSMIC) need the portal so the
compositor delivers the shortcut while another surface is focused.
"""

from __future__ import annotations

import logging
import re
import secrets
from typing import Any, Callable

from ulauncher import show_launcher_label

logger = logging.getLogger(__name__)

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
GLOBAL_SHORTCUTS_IFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"
SHORTCUT_ID = "toggle-ulauncher"
NATIVE_HOTKEY_DESKTOPS = frozenset({"GNOME", "XFCE", "PLASMA"})
HOST_REGISTRY_IFACES = (
    "org.freedesktop.portal.Registry",
    "org.freedesktop.host.portal.Registry",
)

_MOD_MAP = {
    "control": "CTRL",
    "ctrl": "CTRL",
    "primary": "CTRL",
    "shift": "SHIFT",
    "alt": "ALT",
    "mod1": "ALT",
    "super": "SUPER",
    "meta": "SUPER",
    "hyper": "HYPER",
}
_GTK_MOD_RE = re.compile(r"<([^>]+)>")


def should_bind_portal(desktop_id: str | None) -> bool:
    return desktop_id not in NATIVE_HOTKEY_DESKTOPS


def gtk_accel_to_portal_trigger(accel: str) -> str:
    """Map a GTK accelerator such as ``<Control>space`` to ``CTRL+SPACE``."""
    text = (accel or "").strip()
    mods: list[str] = []
    for match in _GTK_MOD_RE.finditer(text):
        mapped = _MOD_MAP.get(match.group(1).lower())
        if mapped and mapped not in mods:
            mods.append(mapped)
    key = _GTK_MOD_RE.sub("", text).strip().replace(" ", "")
    key = key.upper() if key else ""
    if key == " ":
        key = "SPACE"
    parts = [*mods, key] if key else list(mods)
    return "+".join(parts)


def portal_sender_token(unique_name: str) -> str:
    name = unique_name[1:] if unique_name.startswith(":") else unique_name
    return name.replace(".", "_")


def portal_request_path(unique_name: str, handle_token: str) -> str:
    return f"/org/freedesktop/portal/desktop/request/{portal_sender_token(unique_name)}/{handle_token}"


def bind_shortcuts_entries(trigger: str, description: str | None = None) -> list[tuple[str, dict[str, str]]]:
    return [
        (
            SHORTCUT_ID,
            {
                "description": description or show_launcher_label,
                "preferred_trigger": trigger,
            },
        )
    ]


def session_handle_from_response(response_code: int, results: Any) -> str:
    if response_code != 0:
        return ""
    payload = results
    if hasattr(results, "unpack"):
        payload = results.unpack()
    if not isinstance(payload, dict):
        return ""
    handle = payload.get("session_handle", "")
    if hasattr(handle, "get_string"):
        handle = handle.get_string()
    elif hasattr(handle, "unpack"):
        handle = handle.unpack()
    return str(handle or "")


def activated_shortcut_id(args: Any) -> str:
    payload = args.unpack() if hasattr(args, "unpack") else args
    if isinstance(payload, (list, tuple)) and len(payload) >= 2:
        return str(payload[1])
    return ""


def should_toggle_for_activation(shortcut_id: str, expected: str = SHORTCUT_ID) -> bool:
    return shortcut_id == expected


def new_handle_token(prefix: str = "ul") -> str:
    return f"{prefix}{secrets.token_hex(4)}"


class GlobalShortcutsPortal:
    """Keep a portal session alive and invoke *on_activated* for our shortcut."""

    def __init__(self, on_activated: Callable[[], None]) -> None:
        self._on_activated = on_activated
        self._connection: Any = None
        self._session_handle = ""
        self._accel = ""
        self._subs: list[Any] = []

    def start(self, accel: str, application_id: str, bus: Any | None = None) -> bool:
        connection = bus if bus is not None else _session_connection()
        if connection is None:
            return False
        # Close the previous session before minting a new one: the portal keeps the old
        # accelerator grabbed otherwise, so a rebind leaves both combinations opening the
        # launcher and leaks another session on every change.
        self._close_session()
        self._unsubscribe()
        self._connection = connection
        self._accel = accel
        trigger = gtk_accel_to_portal_trigger(accel)
        if not trigger:
            return False
        _register_host_app(connection, application_id)
        unique = _connection_unique_name(connection)
        handle_token = new_handle_token()
        session_token = new_handle_token("uls")
        request_path = portal_request_path(unique, handle_token)
        self._subscribe_request(connection, request_path, self._on_create_session_response)
        self._subscribe_activated(connection)
        return _call_create_session(connection, handle_token, session_token)

    def _on_create_session_response(self, response_code: int, results: Any) -> None:
        handle = session_handle_from_response(response_code, results)
        if not handle or self._connection is None:
            logger.debug("GlobalShortcuts CreateSession did not return a session")
            return
        self._session_handle = handle
        unique = _connection_unique_name(self._connection)
        handle_token = new_handle_token("ulb")
        request_path = portal_request_path(unique, handle_token)
        self._subscribe_request(self._connection, request_path, self._on_bind_response)
        trigger = gtk_accel_to_portal_trigger(self._accel)
        _call_bind_shortcuts(self._connection, handle, trigger, handle_token)

    def _on_bind_response(self, response_code: int, _results: Any) -> None:
        if response_code != 0:
            logger.debug("GlobalShortcuts BindShortcuts was declined or failed")

    def _on_activated_signal(self, args: Any) -> None:
        if should_toggle_for_activation(activated_shortcut_id(args)):
            from ulauncher.utils import scheduling

            scheduling.run_when_idle(self._on_activated)

    def _subscribe_request(self, connection: Any, path: str, handler: Callable[[int, Any], None]) -> None:
        callback = _request_response_callback(handler)
        sub_id = _signal_subscribe(connection, REQUEST_IFACE, "Response", path, callback)
        if sub_id:
            self._subs.append(sub_id)

    def _subscribe_activated(self, connection: Any) -> None:
        callback = _activated_callback(self._on_activated_signal)
        sub_id = _signal_subscribe(connection, GLOBAL_SHORTCUTS_IFACE, "Activated", PORTAL_PATH, callback)
        if sub_id:
            self._subs.append(sub_id)

    def _close_session(self) -> None:
        handle = self._session_handle
        connection = self._connection
        if not handle or connection is None:
            return
        try:
            from PySide6.QtDBus import QDBusMessage

            message = QDBusMessage.createMethodCall(PORTAL_BUS, handle, SESSION_IFACE, "Close")
            connection.asyncCall(message)
        except Exception:
            logger.debug("GlobalShortcuts Session.Close failed", exc_info=True)
        self._session_handle = ""

    def _unsubscribe(self) -> None:
        for subscription in self._subs:
            try:
                subscription.unsubscribe()
            except (TypeError, ValueError, RuntimeError, OSError, AttributeError):
                continue
        self._subs = []
        self._session_handle = ""


def _connection_unique_name(connection: Any) -> str:
    for getter_name in ("baseService", "get_unique_name"):
        getter = getattr(connection, getter_name, None)
        if callable(getter):
            try:
                return str(getter() or "")
            except (TypeError, RuntimeError):
                continue
    return ""


def _session_connection() -> Any | None:
    try:
        from ulauncher.utils import qdbus

        bus = qdbus.session_bus()
        return bus if bus.isConnected() else None
    except Exception:
        logger.debug("No session bus for GlobalShortcuts", exc_info=True)
        return None


def _register_host_app(connection: Any, application_id: str) -> None:
    # xdg-desktop-portal 1.20+ rejects CreateSession from a host app without this.
    try:
        from PySide6.QtDBus import QDBusMessage
    except (ImportError, AttributeError, RuntimeError, OSError):
        return
    for iface in HOST_REGISTRY_IFACES:
        try:
            message = QDBusMessage.createMethodCall(PORTAL_BUS, PORTAL_PATH, iface, "Register")
            message.setArguments([application_id, {}])
            reply = connection.call(message, timeout=200)
            if reply.type() == QDBusMessage.MessageType.ReplyMessage:
                return
            logger.debug("Host Registry.Register failed on %s: %s", iface, reply.errorMessage())
        except Exception:
            logger.debug("Host Registry.Register failed on %s", iface, exc_info=True)
            continue


def _call_create_session(connection: Any, handle_token: str, session_token: str) -> bool:
    try:
        from PySide6.QtDBus import QDBusMessage

        options = {
            "handle_token": handle_token,
            "session_handle_token": session_token,
        }
        message = QDBusMessage.createMethodCall(PORTAL_BUS, PORTAL_PATH, GLOBAL_SHORTCUTS_IFACE, "CreateSession")
        message.setArguments([options])
        connection.asyncCall(message)
        return True
    except Exception:
        logger.debug("GlobalShortcuts CreateSession failed", exc_info=True)
        return False


def _call_bind_shortcuts(connection: Any, session_handle: str, trigger: str, handle_token: str) -> None:
    """BindShortcuts has signature (oa(sa{sv})sa{sv}), which QtDBus cannot infer from
    plain Python values - the shortcuts array must be streamed into a QDBusArgument.
    On failure the shortcut degrades to the DE keybinding / a compositor bind of
    `ulauncher toggle`."""
    try:
        from PySide6.QtCore import QMetaType
        from PySide6.QtDBus import QDBusArgument, QDBusMessage, QDBusObjectPath, QDBusVariant

        entries_arg = QDBusArgument()
        entries_arg.beginArray(QMetaType.Type.UnknownType.value)
        for shortcut_id, fields in bind_shortcuts_entries(trigger):
            entries_arg.beginStructure()
            entries_arg.add(shortcut_id, QMetaType.Type.QString.value)
            entries_arg.beginMap(QMetaType.Type.QString.value, QMetaType.Type.QVariant.value)
            for key, value in fields.items():
                entries_arg.beginMapEntry()
                entries_arg.add(key, QMetaType.Type.QString.value)
                entries_arg.add(QDBusVariant(value))
                entries_arg.endMapEntry()
            entries_arg.endMap()
            entries_arg.endStructure()
        entries_arg.endArray()

        message = QDBusMessage.createMethodCall(PORTAL_BUS, PORTAL_PATH, GLOBAL_SHORTCUTS_IFACE, "BindShortcuts")
        message.setArguments([QDBusObjectPath(session_handle), entries_arg, "", {"handle_token": handle_token}])
        connection.asyncCall(message)
    except Exception:
        logger.debug("GlobalShortcuts BindShortcuts failed", exc_info=True)


def _signal_subscribe(
    connection: Any,
    iface: str,
    member: str,
    path: str,
    callback: Callable[..., None],
) -> Any:
    try:
        from ulauncher.utils import qdbus

        subscription = qdbus.SignalSubscription(connection, "", path, iface, member, callback)
        return subscription if subscription.connected else 0
    except Exception:
        logger.debug("Could not subscribe to %s.%s", iface, member, exc_info=True)
        return 0


def _request_response_callback(handler: Callable[[int, Any], None]) -> Callable[..., None]:
    def _callback(args: Any) -> None:
        from ulauncher.utils import qdbus

        payload = qdbus.unwrap(list(args))
        code = 1
        results: Any = {}
        if isinstance(payload, (list, tuple)) and payload:
            try:
                code = int(payload[0])
            except (TypeError, ValueError):
                code = 1
            results = payload[1] if len(payload) > 1 else {}
        handler(code, results)

    return _callback


def _activated_callback(handler: Callable[[Any], None]) -> Callable[..., None]:
    def _callback(args: Any) -> None:
        from ulauncher.utils import qdbus

        handler(qdbus.unwrap(list(args)))

    return _callback
