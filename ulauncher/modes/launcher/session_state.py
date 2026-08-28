"""Live lock, greeter, and screen-time probes for popupGate.js."""

from __future__ import annotations

import os
from typing import Any, Callable, Mapping

from ulauncher.modes.launcher.popup_gate import session_limits_reached, time_limits_state


def _dbus_call(
    bus_type: str,
    dest: str,
    path: str,
    iface: str,
    method: str,
) -> Any | None:
    try:
        from ulauncher.utils import qdbus

        bus = qdbus.session_bus() if bus_type == "session" else qdbus.system_bus()
        reply = qdbus.call(bus, dest, path, iface, method, timeout_ms=200)
        if reply:
            return reply[0]
        return reply
    except Exception:
        return None


def _screensaver_active() -> bool:
    for dest, path, iface in (
        ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver"),
        ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver"),
    ):
        active = _dbus_call("session", dest, path, iface, "GetActive")
        if active is True:
            return True
    return False


def _logind_locked() -> bool:
    session_id = os.environ.get("XDG_SESSION_ID") or "auto"
    locked = _dbus_call(
        "system",
        "org.freedesktop.login1",
        f"/org/freedesktop/login1/session/{session_id}",
        "org.freedesktop.login1.Session",
        "GetLockedHint",
    )
    return bool(locked)


def session_is_locked(probe: Callable[[], bool] | None = None) -> bool:
    if probe is not None:
        return bool(probe())
    return _screensaver_active() or _logind_locked()


def session_is_greeter(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get("XDG_SESSION_CLASS", "").lower() == "greeter"


def session_limits_reached_now(probe: Callable[[], Any] | None = None) -> bool:
    if probe is not None:
        return session_limits_reached(time_limits_state(probe()))
    from ulauncher.modes.launcher.time_limits import live_limits_reached

    return live_limits_reached()


def session_popup_blockers(
    locked_probe: Callable[[], bool] | None = None,
    greeter_environ: Mapping[str, str] | None = None,
    limits_probe: Callable[[], Any] | None = None,
) -> tuple[bool, bool, bool]:
    return (
        session_is_locked(locked_probe),
        session_is_greeter(greeter_environ),
        session_limits_reached_now(limits_probe),
    )
