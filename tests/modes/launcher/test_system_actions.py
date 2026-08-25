from __future__ import annotations

import pytest

from ulauncher.modes.launcher.system_actions import (
    SYSTEM_ACTIONS,
    action_is_available,
    match_system_actions,
    run_system_action,
    screenshot_commands,
    show_screenshot_ui,
)


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
    assert match_system_actions("sign off")[0]["id"] == "logout"
    assert match_system_actions("lock orientation")[0]["id"] == "lock-orientation"


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


def test_screenshot_icon_matches_goshos() -> None:
    shot = next(action for action in SYSTEM_ACTIONS if action["id"] == "screenshot")
    assert shot["title"] == "Take a Screenshot"
    assert shot["icon"] == "record-screen-symbolic"
    commands = screenshot_commands()
    assert commands[0] == ["gtk-launch", "org.gnome.Screenshot"]
    assert ["gnome-screenshot", "-i"] in commands
    assert ["grim"] in commands
    assert shot["commands"] == commands


def test_screenshot_portal_runs_before_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    assert show_screenshot_ui(lambda: True) is True
    assert show_screenshot_ui(lambda: False) is False
    launched: list[list[str]] = []
    monkeypatch.setattr("ulauncher.modes.launcher.system_actions.launch_detached", launched.append)
    monkeypatch.setattr("ulauncher.modes.launcher.system_actions.shutil.which", lambda exe: exe)
    run_system_action("screenshot", screenshot_ui=lambda: True)
    assert launched == []
    run_system_action("screenshot", screenshot_ui=lambda: False)
    assert launched
    assert launched[0] == ["gtk-launch", "org.gnome.Screenshot"]
