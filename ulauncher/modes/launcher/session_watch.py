"""Watch lock, overview, and sleep while the popup is open (goshos ``_listenSession``)."""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from ulauncher.modes.launcher.system_modal import SYSTEM_MODAL_WATCHES, name_owner_changed_should_close
from ulauncher.modes.launcher.time_limits import (
    MALCONTENT_TIMER_IFACE,
    MALCONTENT_TIMER_SIGNAL,
    TIME_LIMITS_WATCHES,
)

# GNOME sessionMode.updated is in-process. A GTK app gets lock via ScreenSaver D-Bus.
SCREENSAVER_WATCHES = (
    ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged"),
    (
        "org.freedesktop.ScreenSaver",
        "/org/freedesktop/ScreenSaver",
        "org.freedesktop.ScreenSaver",
        "ActiveChanged",
    ),
)

# addTopChrome sits above the overview, so Super must tear the popup down.
OVERVIEW_WATCHES = (
    (
        "org.gnome.Shell",
        "/org/gnome/Shell",
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
    ),
)

# login1 Lock / PrepareForSleep cover greeter handoff and lid-close that ScreenSaver can miss.
LOGIN_WATCHES = (
    (
        "org.freedesktop.login1",
        "/org/freedesktop/login1",
        "org.freedesktop.login1.Manager",
        "PrepareForSleep",
    ),
    (
        "org.freedesktop.login1",
        "/org/freedesktop/login1/session/auto",
        "org.freedesktop.login1.Session",
        "Lock",
    ),
    (
        "org.freedesktop.login1",
        "/org/freedesktop/login1/session/self",
        "org.freedesktop.login1.Session",
        "Lock",
    ),
)

ALL_WATCHES = (
    *SCREENSAVER_WATCHES,
    *OVERVIEW_WATCHES,
    *LOGIN_WATCHES,
    *TIME_LIMITS_WATCHES,
    *SYSTEM_MODAL_WATCHES,
)


def next_session_watch_action(was_listening: bool, want_listening: bool) -> str:
    if want_listening and not was_listening:
        return "start"
    if not want_listening and was_listening:
        return "stop"
    return "keep"


def screensaver_active_changed_should_close(active: object) -> bool:
    return bool(active)


def _unpack(value: Any) -> Any:
    unpacked = value.unpack() if hasattr(value, "unpack") else value
    return unpacked


def _changed_properties(changed: Any) -> dict[str, Any]:
    payload = _unpack(changed)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, (list, tuple)):
        result: dict[str, Any] = {}
        for item in payload:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result[str(item[0])] = item[1]
        return result
    return {}


def _prop_is_true(value: Any) -> bool:
    payload = _unpack(value)
    if isinstance(payload, (list, tuple)):
        payload = payload[0] if payload else False
    return bool(payload)


def properties_changed_should_close(iface: str, changed: Any) -> bool:
    props = _changed_properties(changed)
    if iface == "org.gnome.Shell" and "OverviewActive" in props:
        return _prop_is_true(props["OverviewActive"])
    if iface in {"org.freedesktop.login1.Session", "org.freedesktop.login1.Manager"} and "LockedHint" in props:
        return _prop_is_true(props["LockedHint"])
    return False


def session_signal_should_close(interface_name: str, signal_name: str, args: Any) -> bool:
    payload = _unpack(args)
    if signal_name == "ActiveChanged":
        if interface_name not in {"org.gnome.ScreenSaver", "org.freedesktop.ScreenSaver"}:
            return False
        if isinstance(payload, (list, tuple)):
            active = payload[0] if payload else False
        else:
            active = payload
        return screensaver_active_changed_should_close(active)
    if signal_name == "Lock":
        return interface_name == "org.freedesktop.login1.Session"
    if signal_name == "PrepareForSleep":
        if interface_name != "org.freedesktop.login1.Manager":
            return False
        if isinstance(payload, (list, tuple)):
            sleeping = payload[0] if payload else False
        else:
            sleeping = payload
        return bool(sleeping)
    if signal_name == "PropertiesChanged":
        if isinstance(payload, (list, tuple)) and payload:
            iface = str(payload[0])
            changed = payload[1] if len(payload) > 1 else {}
            return properties_changed_should_close(iface, changed)
        return False
    if signal_name == "NameOwnerChanged":
        if interface_name != "org.freedesktop.DBus":
            return False
        if isinstance(payload, (list, tuple)) and len(payload) >= 3:
            return name_owner_changed_should_close(payload[0], payload[1], payload[2])
        return False
    return False


class SessionWatcher:
    """Subscribe to lock/overview/sleep signals and close the popup."""

    def __init__(
        self,
        on_close: Callable[[], None],
        subscribe: Callable[..., int] | None = None,
        limits_reached: Callable[[], bool] | None = None,
    ) -> None:
        self._on_close = on_close
        self._subscribe = subscribe
        self._limits_reached = limits_reached
        self._listening = False
        self._ids: list[tuple[Any, int]] = []

    @property
    def listening(self) -> bool:
        return self._listening

    def start(self) -> None:
        if next_session_watch_action(self._listening, True) != "start":
            return
        self._listening = True
        if self._subscribe is not None:
            for dest, path, iface, member in ALL_WATCHES:
                sub_id = self._subscribe(dest, path, iface, member, self._on_signal)
                if sub_id:
                    self._ids.append((None, int(sub_id)))
            return
        self._subscribe_dbus()

    def stop(self) -> None:
        if next_session_watch_action(self._listening, False) != "stop":
            return
        for bus, sub_id in self._ids:
            if bus is not None:
                with contextlib.suppress(TypeError, RuntimeError, OSError, AttributeError):
                    bus.signal_unsubscribe(sub_id)
        self._ids = []
        self._listening = False

    def _on_signal(self, interface_name: str, signal_name: str, args: Any) -> None:
        if signal_name == MALCONTENT_TIMER_SIGNAL and interface_name == MALCONTENT_TIMER_IFACE:
            # gnome-shell re-probes GetEstimatedTimes; the signal itself is not LIMIT_REACHED
            probe = self._limits_reached
            if probe is None:
                from ulauncher.modes.launcher.session_state import session_limits_reached_now

                probe = session_limits_reached_now
            if probe():
                self._on_close()
            return
        if session_signal_should_close(interface_name, signal_name, args):
            self._on_close()

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
            args = params.unpack() if hasattr(params, "unpack") else params
            self._on_signal(iface, member, args)

        system_names = {"org.freedesktop.login1", "org.freedesktop.MalcontentTimer1"}
        for dest, path, iface, member in ALL_WATCHES:
            connection = _bus_for_dest(Gio, bus, dest, system_names)
            if connection is None:
                continue
            sub_id = _subscribe_signal(connection, Gio, dest, path, iface, member, _callback)
            if sub_id:
                self._ids.append((connection, int(sub_id)))


def _bus_for_dest(gio: Any, session_bus: Any, dest: str, system_names: set[str]) -> Any | None:
    if dest not in system_names:
        return session_bus
    with contextlib.suppress(Exception):
        return gio.bus_get_sync(gio.BusType.SYSTEM, None)
    return None


def _subscribe_signal(
    connection: Any,
    gio: Any,
    dest: str,
    path: str,
    iface: str,
    member: str,
    callback: Callable[..., None],
) -> int:
    with contextlib.suppress(Exception):
        sub_id = connection.signal_subscribe(
            dest,
            iface,
            member,
            path,
            None,
            gio.DBusSignalFlags.NONE,
            callback,
        )
        return int(sub_id or 0)
    return 0
