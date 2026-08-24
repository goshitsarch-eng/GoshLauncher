"""GNOME 46+ screen-time / malcontent mapping for goshos ``_listenTimeLimits``.

gnome-shell's TimeLimitsManager is in-process. A GTK app gets the parental half
from malcontent-timerd: GetEstimatedTimes('login-session') returns a map whose
empty-string row is [?, currentSessionStart, currentSessionEnd, nextSessionStart].
LIMIT_REACHED iff now >= currentSessionEnd. EstimatedTimesChanged only means
"re-probe"; it is not itself a close.

Wellbeing (org.gnome.desktop.screen-time-limits) needs gnome-shell's
session-active-history.json plus idle/lock tracking. Enabling the setting
without that history must not be treated as LIMIT_REACHED.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from ulauncher.modes.launcher.popup_gate import TIME_LIMITS_REACHED

TIME_LIMITS_DISABLED = 0
TIME_LIMITS_ACTIVE = 1

MALCONTENT_TIMER_DEST = "org.freedesktop.MalcontentTimer1"
MALCONTENT_TIMER_PATH = "/org/freedesktop/MalcontentTimer1"
MALCONTENT_TIMER_IFACE = "org.freedesktop.MalcontentTimer1.Child"
MALCONTENT_TIMER_SIGNAL = "EstimatedTimesChanged"
LOGIN_SESSION = "login-session"

TIME_LIMITS_WATCHES = (
    (
        MALCONTENT_TIMER_DEST,
        MALCONTENT_TIMER_PATH,
        MALCONTENT_TIMER_IFACE,
        MALCONTENT_TIMER_SIGNAL,
    ),
)


def _unpack(value: Any) -> Any:
    payload = value.unpack() if hasattr(value, "unpack") else value
    while isinstance(payload, (list, tuple)) and len(payload) == 1:
        inner = payload[0]
        payload = inner.unpack() if hasattr(inner, "unpack") else inner
    return payload


def malcontent_times_from_reply(reply: Any) -> dict[str, Any]:
    payload = _unpack(reply)
    if isinstance(payload, (list, tuple)) and len(payload) >= 2 and isinstance(payload[1], dict):
        payload = payload[1]
    if isinstance(payload, dict):
        return payload
    return {}


def malcontent_times_to_state(now: float, times: Mapping[str, Any] | None) -> int:
    if not times:
        return TIME_LIMITS_DISABLED
    row: Any = times.get("")
    if row is None:
        return TIME_LIMITS_DISABLED
    row = _unpack(row)
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 3:
        return TIME_LIMITS_DISABLED
    current_end = float(row[2])
    if current_end <= 0:
        return TIME_LIMITS_DISABLED
    if now >= current_end:
        return TIME_LIMITS_REACHED
    return TIME_LIMITS_ACTIVE


def wellbeing_settings_to_state(
    daily_limit_enabled: bool,
    daily_limit_seconds: float,
    active_today_seconds: float | None,
) -> int:
    """Map wellbeing GSettings onto TimeLimitsState without inventing history.

    ``active_today_seconds is None`` means this process cannot see gnome-shell's
    session-active-history, so the result stays DISABLED even if the setting is on.
    """
    if not daily_limit_enabled:
        return TIME_LIMITS_DISABLED
    if active_today_seconds is None:
        return TIME_LIMITS_DISABLED
    if daily_limit_seconds > 0 and active_today_seconds >= daily_limit_seconds:
        return TIME_LIMITS_REACHED
    return TIME_LIMITS_ACTIVE


def live_limits_reached(
    now: float | None = None,
    times_probe: Callable[[], Mapping[str, Any] | None] | None = None,
) -> bool:
    import time

    now_secs = time.time() if now is None else now
    probe = times_probe or probe_malcontent_estimated_times
    return malcontent_times_to_state(now_secs, probe()) == TIME_LIMITS_REACHED


def probe_malcontent_estimated_times() -> dict[str, Any]:
    try:
        from ulauncher.gi import Gio, GLib
    except (ImportError, AttributeError, RuntimeError, OSError):
        return {}
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        result = connection.call_sync(
            MALCONTENT_TIMER_DEST,
            MALCONTENT_TIMER_PATH,
            MALCONTENT_TIMER_IFACE,
            "GetEstimatedTimes",
            GLib.Variant("(s)", (LOGIN_SESSION,)),
            None,
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
        return malcontent_times_from_reply(result)
    except Exception:
        return {}
