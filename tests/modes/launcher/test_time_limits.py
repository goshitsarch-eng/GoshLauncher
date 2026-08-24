from __future__ import annotations

from ulauncher.modes.launcher.popup_gate import TIME_LIMITS_REACHED
from ulauncher.modes.launcher.time_limits import (
    LOGIN_SESSION,
    MALCONTENT_TIMER_DEST,
    MALCONTENT_TIMER_IFACE,
    MALCONTENT_TIMER_PATH,
    MALCONTENT_TIMER_SIGNAL,
    TIME_LIMITS_ACTIVE,
    TIME_LIMITS_DISABLED,
    TIME_LIMITS_WATCHES,
    live_limits_reached,
    malcontent_times_from_reply,
    malcontent_times_to_state,
    wellbeing_settings_to_state,
)


def test_malcontent_times_to_state_matches_gnome_shell() -> None:
    now = 1_700_000_000.0
    assert malcontent_times_to_state(now, None) == TIME_LIMITS_DISABLED
    assert malcontent_times_to_state(now, {}) == TIME_LIMITS_DISABLED
    assert malcontent_times_to_state(now, {"": (0.0, now - 10, 0.0, now + 10)}) == TIME_LIMITS_DISABLED
    assert malcontent_times_to_state(now, {"": (0.0, now - 10, now + 60, now + 3600)}) == TIME_LIMITS_ACTIVE
    assert malcontent_times_to_state(now, {"": (0.0, now - 10, now, now + 3600)}) == TIME_LIMITS_REACHED
    assert malcontent_times_to_state(now + 1, {"": (0.0, now - 10, now, now + 3600)}) == TIME_LIMITS_REACHED


def test_malcontent_reply_unwraps_gjs_tuple() -> None:
    times = malcontent_times_from_reply((True, {"": (0.0, 1.0, 2.0, 3.0)}))
    assert times[""][2] == 2.0
    assert malcontent_times_from_reply({"": (0.0, 1.0, 2.0, 3.0)})[""][1] == 1.0
    assert malcontent_times_from_reply(None) == {}


def test_wellbeing_does_not_false_positive_without_history() -> None:
    assert wellbeing_settings_to_state(False, 3600, None) == TIME_LIMITS_DISABLED
    assert wellbeing_settings_to_state(True, 3600, None) == TIME_LIMITS_DISABLED
    assert wellbeing_settings_to_state(True, 3600, 1200) == TIME_LIMITS_ACTIVE
    assert wellbeing_settings_to_state(True, 3600, 3600) == TIME_LIMITS_REACHED


def test_live_limits_reached_uses_injected_times() -> None:
    now = 100.0
    assert live_limits_reached(now, lambda: {"": (0.0, 10.0, 200.0, 400.0)}) is False
    assert live_limits_reached(now, lambda: {"": (0.0, 10.0, 50.0, 400.0)}) is True
    assert TIME_LIMITS_WATCHES == (
        (MALCONTENT_TIMER_DEST, MALCONTENT_TIMER_PATH, MALCONTENT_TIMER_IFACE, MALCONTENT_TIMER_SIGNAL),
    )
    assert LOGIN_SESSION == "login-session"
