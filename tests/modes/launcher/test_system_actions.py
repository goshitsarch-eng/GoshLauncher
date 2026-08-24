from __future__ import annotations

from ulauncher.modes.launcher.system_actions import action_is_available, match_system_actions


def test_spoken_lock_sign_out_and_power_off() -> None:
    lock = match_system_actions("lock the screen")
    assert lock
    assert lock[0]["id"] == "lock"
    logout = match_system_actions("sign out")
    assert logout
    assert logout[0]["id"] == "logout"
    power = match_system_actions("power off")
    assert power
    assert power[0]["id"] == "shutdown"
    shutdown = match_system_actions("shut down the computer")
    assert shutdown
    assert shutdown[0]["id"] == "shutdown"
    assert match_system_actions("lock now")
    assert match_system_actions("sleep")


def test_logind_no_hides_power_actions_screenshot_stays() -> None:
    denied = {"CanPowerOff": "no", "CanReboot": "na", "CanSuspend": "no"}
    assert action_is_available("shutdown", denied) is False
    assert action_is_available("restart", denied) is False
    assert action_is_available("suspend", denied) is False
    assert action_is_available("screenshot", denied) is True
    assert action_is_available("lock", denied) is True
    assert match_system_actions("power off", can_map=denied) == []
    allowed = {"CanPowerOff": "challenge"}
    assert action_is_available("shutdown", allowed) is True
    assert match_system_actions("power off", can_map=allowed)
