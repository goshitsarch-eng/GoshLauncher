"""Phosh OSK0 stand-in for goshos ``_listenKeyboard``.

gnome-shell's keyboardBox is in-process (visible, allocation, translation-y).
A GTK app cannot see that actor. sm.puri.OSK0 Visible is the public D-Bus
equivalent on Phosh; the daemon does not publish height, so the keyboard is
modeled as a bottom strip of min(360px, 1/3 of the work area). Changing
Visible repositions the popup and must not close it.
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable

PHOSH_OSK_DEST = "sm.puri.OSK0"
PHOSH_OSK_PATH = "/sm/puri/OSK0"
PHOSH_OSK_IFACE = "sm.puri.OSK0"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

OSK_WATCHES = ((PHOSH_OSK_DEST, PHOSH_OSK_PATH, PROPERTIES_IFACE, "PropertiesChanged"),)

_DEFAULT_OSK_HEIGHT = 360.0
_DEFAULT_OSK_FRACTION = 1.0 / 3.0


def next_osk_watch_action(was_listening: bool, want_listening: bool) -> str:
    if want_listening and not was_listening:
        return "start"
    if not want_listening and was_listening:
        return "stop"
    return "keep"


def _unpack(value: Any) -> Any:
    payload = value.unpack() if hasattr(value, "unpack") else value
    while isinstance(payload, (list, tuple)) and len(payload) == 1:
        inner = payload[0]
        payload = inner.unpack() if hasattr(inner, "unpack") else inner
    return payload


def _as_bool(value: Any) -> bool:
    payload = _unpack(value)
    if isinstance(payload, (list, tuple)):
        payload = payload[0] if payload else False
    return bool(payload)


def osk_visible_from_changed(changed: Any) -> bool | None:
    payload = _unpack(changed)
    if not isinstance(payload, dict) or "Visible" not in payload:
        return None
    return _as_bool(payload["Visible"])


def osk_visible_from_properties_changed(_interface_name: str, signal_name: str, args: Any) -> bool | None:
    if signal_name != "PropertiesChanged":
        return None
    payload = _unpack(args)
    if not isinstance(payload, (list, tuple)) or not payload:
        return None
    iface = str(payload[0])
    if iface not in {PHOSH_OSK_IFACE, PROPERTIES_IFACE}:
        return None
    changed = payload[1] if len(payload) > 1 else {}
    visible = osk_visible_from_changed(changed)
    if visible is not None:
        return visible
    if iface == PROPERTIES_IFACE and len(payload) > 1:
        return osk_visible_from_changed(payload[1])
    return None


def osk_height_for_work_area(work_area: dict[str, float], height: float | None = None) -> float:
    if height is not None and height > 0:
        return float(height)
    work_height = float(work_area.get("height") or 0)
    if work_height <= 0:
        return _DEFAULT_OSK_HEIGHT
    return min(_DEFAULT_OSK_HEIGHT, work_height * _DEFAULT_OSK_FRACTION)


def osk_keyboard_for_work_area(
    work_area: dict[str, float],
    visible: bool,
    height: float | None = None,
    monitor_index: int = 0,
) -> dict[str, Any]:
    if not visible:
        return {
            "visible": False,
            "y": 0,
            "height": 0,
            "translationY": 0,
            "monitorIndex": -1,
            "workMonitorIndex": monitor_index,
        }
    kb_height = osk_height_for_work_area(work_area, height)
    return {
        "visible": True,
        "y": work_area["y"] + work_area["height"] - kb_height,
        "height": kb_height,
        "translationY": 0,
        "monitorIndex": monitor_index,
        "workMonitorIndex": monitor_index,
    }


def probe_osk_visible() -> bool:
    try:
        from ulauncher.gi import Gio, GLib
    except (ImportError, AttributeError, RuntimeError, OSError):
        return False
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            PHOSH_OSK_DEST,
            PHOSH_OSK_PATH,
            PROPERTIES_IFACE,
            "Get",
            GLib.Variant("(ss)", (PHOSH_OSK_IFACE, "Visible")),
            None,
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
        return _as_bool(result)
    except Exception:
        return False


class OskWatcher:
    """Subscribe to Phosh OSK0 Visible and report changes. Never closes the popup."""

    def __init__(
        self,
        on_changed: Callable[[bool], None],
        subscribe: Callable[..., int] | None = None,
        visible_probe: Callable[[], bool] | None = None,
    ) -> None:
        self._on_changed = on_changed
        self._subscribe = subscribe
        self._visible_probe = visible_probe
        self._listening = False
        self._ids: list[tuple[Any, int]] = []
        self.visible = False

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if next_osk_watch_action(self._listening, True) != "start":
            return
        self._listening = True
        probe = self._visible_probe or probe_osk_visible
        self.visible = bool(probe())
        if self._subscribe is not None:
            for dest, path, iface, member in OSK_WATCHES:
                sub_id = self._subscribe(dest, path, iface, member, self._on_signal)
                if sub_id:
                    self._ids.append((None, int(sub_id)))
            return
        self._subscribe_dbus()

    def stop(self) -> None:
        if next_osk_watch_action(self._listening, False) != "stop":
            return
        for bus, sub_id in self._ids:
            if bus is not None:
                with contextlib.suppress(TypeError, RuntimeError, OSError, AttributeError):
                    bus.signal_unsubscribe(sub_id)
        self._ids = []
        self._listening = False

    def _on_signal(self, interface_name: str, signal_name: str, args: Any) -> None:
        visible = osk_visible_from_properties_changed(interface_name, signal_name, args)
        if visible is None or visible == self.visible:
            return
        self.visible = visible
        self._on_changed(visible)

    def _subscribe_dbus(self) -> None:
        try:
            from ulauncher.gi import Gio
        except (ImportError, AttributeError, RuntimeError, OSError):
            return
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            return

        def _callback(
            _connection: Any,
            _sender: str,
            _path: str,
            iface: str,
            member: str,
            params: Any,
            *_user: object,
        ) -> None:
            unpacked = params.unpack() if hasattr(params, "unpack") else params
            self._on_signal(iface, member, unpacked)

        for dest, path, iface, member in OSK_WATCHES:
            with contextlib.suppress(Exception):
                sub_id = bus.signal_subscribe(
                    dest,
                    iface,
                    member,
                    path,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    _callback,
                )
                if sub_id:
                    self._ids.append((bus, int(sub_id)))
