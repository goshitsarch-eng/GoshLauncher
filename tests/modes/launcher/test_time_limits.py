from __future__ import annotations

import json
from pathlib import Path

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
    live_wellbeing_state,
    load_wellbeing_history,
    malcontent_times_from_reply,
    malcontent_times_to_state,
    parse_wellbeing_history,
    seconds_until_limit,
    start_of_local_day,
    wellbeing_active_seconds_today,
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


def test_wellbeing_history_matches_gnome_shell_active_time(tmp_path: Path) -> None:
    now = start_of_local_day(1_700_100_000.0) + 3600
    start = start_of_local_day(now)
    finished = [
        {"oldState": 0, "newState": 1, "wallTimeSecs": start},
        {"oldState": 1, "newState": 0, "wallTimeSecs": start + 1200},
    ]
    assert wellbeing_active_seconds_today(now, finished) == 1200
    still_active = [{"oldState": 0, "newState": 1, "wallTimeSecs": start + 100}]
    assert wellbeing_active_seconds_today(start + 400, still_active) == 300
    overnight = [{"oldState": 1, "newState": 0, "wallTimeSecs": start + 60}]
    assert wellbeing_active_seconds_today(start + 120, overnight) == 60
    assert parse_wellbeing_history("[]") == []
    assert parse_wellbeing_history('{"nope": 1}') == []
    parsed = parse_wellbeing_history(json.dumps(finished))
    assert parsed[0]["newState"] == 1
    missing = tmp_path / "missing.json"
    assert load_wellbeing_history(missing) is None
    bogus = tmp_path / "bogus.json"
    bogus.write_text("not-json", encoding="utf-8")
    assert load_wellbeing_history(bogus) is None
    history_file = tmp_path / "session-active-history.json"
    history_file.write_text(json.dumps(finished), encoding="utf-8")
    loaded = load_wellbeing_history(history_file)
    assert loaded is not None
    assert live_wellbeing_state(now, lambda: (True, 600), lambda: loaded) == TIME_LIMITS_REACHED
    assert live_wellbeing_state(now, lambda: (True, 10_000), lambda: loaded) == TIME_LIMITS_ACTIVE
    assert live_wellbeing_state(now, lambda: (True, 3600), lambda: None) == TIME_LIMITS_DISABLED
    assert live_wellbeing_state(now, lambda: None, lambda: loaded) == TIME_LIMITS_DISABLED


def test_live_limits_reached_uses_injected_times() -> None:
    now = 100.0
    assert live_limits_reached(now, lambda: {"": (0.0, 10.0, 200.0, 400.0)}, lambda: TIME_LIMITS_DISABLED) is False
    assert live_limits_reached(now, lambda: {"": (0.0, 10.0, 50.0, 400.0)}, lambda: TIME_LIMITS_DISABLED) is True
    assert live_limits_reached(now, dict, lambda: TIME_LIMITS_REACHED) is True
    assert TIME_LIMITS_WATCHES == (
        (MALCONTENT_TIMER_DEST, MALCONTENT_TIMER_PATH, MALCONTENT_TIMER_IFACE, MALCONTENT_TIMER_SIGNAL),
    )
    assert LOGIN_SESSION == "login-session"


def test_seconds_until_limit_uses_malcontent_wellbeing_and_midnight() -> None:
    now = start_of_local_day(1_700_100_000.0) + 100
    assert seconds_until_limit(now, lambda: {"": (0.0, now - 10, now + 50, now + 400)}, lambda: None) == 50
    assert seconds_until_limit(now, lambda: {"": (0.0, now - 10, now - 1, now + 400)}, lambda: None) == 0.0
    assert seconds_until_limit(now, dict, lambda: None) is None
    assert seconds_until_limit(now, dict, lambda: 12.0) == 12.0
    far = start_of_local_day(now) + 86400 + 500
    remaining = seconds_until_limit(now, lambda: {"": (0.0, now - 10, far, far + 10)}, lambda: None)
    assert remaining == start_of_local_day(now) + 86400 - now
