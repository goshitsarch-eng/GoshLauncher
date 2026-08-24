from __future__ import annotations

from ulauncher.modes.launcher.popup_gate import TIME_LIMITS_REACHED, can_open_popup, should_close_on_session
from ulauncher.modes.launcher.session_state import (
    session_is_greeter,
    session_is_locked,
    session_limits_reached_now,
    session_popup_blockers,
)


def test_session_probes_are_injectable() -> None:
    assert session_is_locked(lambda: True) is True
    assert session_is_locked(lambda: False) is False
    assert session_is_greeter({"XDG_SESSION_CLASS": "greeter"}) is True
    assert session_is_greeter({"XDG_SESSION_CLASS": "user"}) is False
    assert session_limits_reached_now(lambda: {"state": TIME_LIMITS_REACHED}) is True
    assert session_limits_reached_now(lambda: {"state": 0}) is False
    locked, greeter, limits = session_popup_blockers(
        locked_probe=lambda: True,
        greeter_environ={"XDG_SESSION_CLASS": "user"},
        limits_probe=lambda: {"state": 0},
    )
    assert (locked, greeter, limits) == (True, False, False)
    assert can_open_popup(False, False, locked, greeter, limits) is False
    assert should_close_on_session(locked, greeter, limits) is True
    assert can_open_popup(False, False, False, False, False) is True
