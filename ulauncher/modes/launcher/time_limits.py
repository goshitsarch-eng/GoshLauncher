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

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ulauncher.modes.launcher.popup_gate import TIME_LIMITS_REACHED

TIME_LIMITS_DISABLED = 0
TIME_LIMITS_ACTIVE = 1

MALCONTENT_TIMER_DEST = "org.freedesktop.MalcontentTimer1"
MALCONTENT_TIMER_PATH = "/org/freedesktop/MalcontentTimer1"
MALCONTENT_TIMER_IFACE = "org.freedesktop.MalcontentTimer1.Child"
MALCONTENT_TIMER_SIGNAL = "EstimatedTimesChanged"
LOGIN_SESSION = "login-session"
WELLBEING_SCHEMA = "org.gnome.desktop.screen-time-limits"
USER_STATE_INACTIVE = 0
USER_STATE_ACTIVE = 1
WELLBEING_HISTORY_NAME = "session-active-history.json"

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


def wellbeing_history_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    data_home = env.get("XDG_DATA_HOME") or str(Path(env.get("HOME") or Path.home()) / ".local" / "share")
    return Path(data_home) / "gnome-shell" / WELLBEING_HISTORY_NAME


def start_of_local_day(now: float) -> float:
    local = datetime.fromtimestamp(now, tz=timezone.utc).astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def wellbeing_active_seconds_today(now: float, entries: Sequence[Mapping[str, Any]]) -> float:
    """Port of gnome-shell TimeLimitsManager._calculateActiveTimeTodaySecs."""
    start_of_today = start_of_local_day(now)
    first_today = -1
    for index, entry in enumerate(entries):
        if float(entry.get("wallTimeSecs") or 0) >= start_of_today:
            first_today = index
            break
    active_today = 0.0
    active_start = start_of_today
    if first_today >= 0:
        for entry in entries[first_today:]:
            new_state = int(entry.get("newState") or 0)
            old_state = int(entry.get("oldState") or 0)
            wall = float(entry.get("wallTimeSecs") or 0)
            if new_state == USER_STATE_ACTIVE:
                active_start = wall
            elif old_state == USER_STATE_ACTIVE:
                active_today += max(wall - active_start, 0.0)
    if entries and int(entries[-1].get("newState") or 0) == USER_STATE_ACTIVE:
        active_today += max(now - active_start, 0.0)
    return max(active_today, 0.0)


def parse_wellbeing_history(raw: str) -> list[dict[str, Any]]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        return []
    entries: list[dict[str, Any]] = []
    previous_wall = 0.0
    for item in payload:
        if not isinstance(item, dict):
            return []
        if "oldState" not in item or "newState" not in item or "wallTimeSecs" not in item:
            return []
        old_state = int(item["oldState"])
        new_state = int(item["newState"])
        wall = float(item["wallTimeSecs"])
        if old_state not in {USER_STATE_INACTIVE, USER_STATE_ACTIVE}:
            return []
        if new_state not in {USER_STATE_INACTIVE, USER_STATE_ACTIVE}:
            return []
        if old_state == new_state or wall < previous_wall:
            return []
        entries.append({"oldState": old_state, "newState": new_state, "wallTimeSecs": wall})
        previous_wall = wall
    return entries


def load_wellbeing_history(path: Path | None = None) -> list[dict[str, Any]] | None:
    history_path = wellbeing_history_path() if path is None else path
    try:
        raw = history_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return parse_wellbeing_history(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def probe_wellbeing_settings() -> tuple[bool, float] | None:
    """Return (daily_limit_enabled, daily_limit_seconds) or None if the schema is missing."""
    import subprocess

    def _gsettings_get(key: str) -> str:
        return subprocess.check_output(
            ["gsettings", "get", WELLBEING_SCHEMA, key], text=True, stderr=subprocess.DEVNULL, timeout=2
        ).strip()

    try:
        history_enabled = _gsettings_get("history-enabled") == "true"
        daily_enabled = _gsettings_get("daily-limit-enabled") == "true"
        daily_seconds = float(_gsettings_get("daily-limit-seconds").split()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        # Schema missing (non-GNOME session) or no gsettings CLI
        return None
    if not history_enabled or not daily_enabled:
        return (False, daily_seconds)
    return (True, daily_seconds)


def live_wellbeing_state(
    now: float,
    settings_probe: Callable[[], tuple[bool, float] | None] | None = None,
    history_probe: Callable[[], Sequence[Mapping[str, Any]] | None] | None = None,
) -> int:
    settings = (settings_probe or probe_wellbeing_settings)()
    if settings is None:
        return TIME_LIMITS_DISABLED
    enabled, limit_seconds = settings
    history = (history_probe or load_wellbeing_history)()
    active = None if history is None else wellbeing_active_seconds_today(now, history)
    return wellbeing_settings_to_state(enabled, limit_seconds, active)


def live_limits_reached(
    now: float | None = None,
    times_probe: Callable[[], Mapping[str, Any] | None] | None = None,
    wellbeing_probe: Callable[[], int] | None = None,
) -> bool:
    import time

    now_secs = time.time() if now is None else now
    probe = times_probe or probe_malcontent_estimated_times
    if malcontent_times_to_state(now_secs, probe()) == TIME_LIMITS_REACHED:
        return True
    wellbeing_state = wellbeing_probe() if wellbeing_probe is not None else live_wellbeing_state(now_secs)
    return wellbeing_state == TIME_LIMITS_REACHED


def seconds_until_limit(
    now: float | None = None,
    times_probe: Callable[[], Mapping[str, Any] | None] | None = None,
    wellbeing_remaining_probe: Callable[[], float | None] | None = None,
) -> float | None:
    """Seconds until LIMIT_REACHED, or None if no limit applies."""
    import time

    now_secs = time.time() if now is None else now
    waits: list[float] = []
    times = (times_probe or probe_malcontent_estimated_times)()
    mal_state = malcontent_times_to_state(now_secs, times)
    if mal_state == TIME_LIMITS_REACHED:
        return 0.0
    row = times.get("") if times else None
    row = _unpack(row) if row is not None else None
    if (
        mal_state == TIME_LIMITS_ACTIVE
        and isinstance(row, Sequence)
        and not isinstance(row, (str, bytes))
        and len(row) >= 3
    ):
        remaining = float(row[2]) - now_secs
        if remaining > 0:
            waits.append(remaining)
    if wellbeing_remaining_probe is not None:
        remaining_wb = wellbeing_remaining_probe()
        if remaining_wb is not None:
            waits.append(max(remaining_wb, 0.0))
    else:
        settings = probe_wellbeing_settings()
        history = load_wellbeing_history()
        if settings is not None and history is not None:
            enabled, limit_seconds = settings
            if enabled and limit_seconds > 0:
                active = wellbeing_active_seconds_today(now_secs, history)
                waits.append(max(limit_seconds - active, 0.0))
    if not waits:
        return None
    until_midnight = start_of_local_day(now_secs) + 86400 - now_secs
    return min(*waits, max(until_midnight, 0.0))


def probe_malcontent_estimated_times() -> dict[str, Any]:
    try:
        from ulauncher.utils import qdbus

        result = qdbus.call(
            qdbus.system_bus(),
            MALCONTENT_TIMER_DEST,
            MALCONTENT_TIMER_PATH,
            MALCONTENT_TIMER_IFACE,
            "GetEstimatedTimes",
            [LOGIN_SESSION],
            timeout_ms=200,
        )
        if result is None:
            return {}
        return malcontent_times_from_reply(result)
    except Exception:
        return {}
