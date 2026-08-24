from __future__ import annotations

from ulauncher.modes.launcher.shortcut import (
    hotkey_to_restore_after_failed_grab,
    shortcut_attempts,
    shortcut_retry_list,
    shortcut_to_persist,
)


def test_shortcut_attempts_include_fallbacks() -> None:
    attempts = shortcut_attempts("<Super>space")
    assert attempts[0] == "<Super>space"
    assert "<Control>space" in attempts
    assert "<Alt>space" in attempts


def test_shortcut_retry_list_keeps_working_grab() -> None:
    assert shortcut_retry_list("<Super>space", "<Control>space") == []
    retries = shortcut_retry_list("<Super>space", "")
    assert retries
    assert "<Super>space" not in retries


def test_shortcut_to_persist_only_when_fallback_worked() -> None:
    assert shortcut_to_persist("<Super>space", "<Super>space") is None
    assert shortcut_to_persist("<Super>space", "<Control>space") == "<Control>space"
    assert shortcut_to_persist("<Super>space", None) is None


def test_hotkey_restore_after_failed_grab_keeps_previous() -> None:
    assert hotkey_to_restore_after_failed_grab(True, "<Control>space") is None
    assert hotkey_to_restore_after_failed_grab(False, "") is None
    assert hotkey_to_restore_after_failed_grab(False, "<Control>space") == "<Control>space"
