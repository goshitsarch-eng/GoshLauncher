from __future__ import annotations

from ulauncher.modes.launcher.shortcut import (
    accelerator_grab_flags,
    build_accelerator,
    format_accelerator,
    format_shortcut_list,
    grab_entries_to_drop,
    grab_release_steps,
    hotkey_to_restore_after_failed_grab,
    is_modifier_key_name,
    modifiers_from_mask,
    normalize_accel_key,
    run_grab_release,
    shortcut_attempts,
    shortcut_display_label,
    shortcut_label_after_change,
    shortcut_retry_list,
    shortcut_to_persist,
    should_ignore_shortcut_repeat,
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


def test_accelerator_build_and_format_match_goshos() -> None:
    assert normalize_accel_key("A") == "a"
    assert normalize_accel_key("space") == "space"
    assert (
        build_accelerator(
            "space",
            {"super": False, "control": True, "shift": False, "alt": False, "meta": False},
        )
        == "<Control>space"
    )
    assert (
        build_accelerator(
            "space",
            {"super": True, "control": False, "shift": False, "alt": False, "meta": True},
        )
        == "<Super>space"
    )
    assert (
        build_accelerator(
            "A",
            {"super": False, "control": True, "shift": True, "alt": False, "meta": False},
        )
        == "<Control><Shift>a"
    )
    assert format_accelerator("<Control>space") == "Ctrl+space"
    assert format_accelerator("<Super><Shift>a") == "Super+Shift+a"
    assert format_shortcut_list([]) == ""
    assert format_shortcut_list(["<Alt>space"]) == "Alt+space"
    mods = modifiers_from_mask(0b101, {"super": 1, "control": 4, "shift": 2, "alt": 8, "meta": 16})
    assert mods["super"]
    assert mods["control"]
    assert not mods["shift"]
    assert is_modifier_key_name("Meta_L")
    assert is_modifier_key_name("ISO_Level3_Shift")
    assert not is_modifier_key_name("space")
    assert shortcut_display_label([]) == "Not set (will default to Ctrl+Space)"
    assert shortcut_display_label(["<Alt>space"]) == "Alt+space"
    assert shortcut_label_after_change(["<Control>space"], True) is None
    assert shortcut_label_after_change(["<Control>space"], False) == "Ctrl+space"
    assert accelerator_grab_flags({"IGNORE_AUTOREPEAT": 16}) == 16
    assert accelerator_grab_flags({}) == 0
    assert accelerator_grab_flags(None) == 0
    assert ",".join(step["kind"] for step in grab_release_steps("gosh-toggle", 42)) == "allow-none,ungrab"
    assert grab_release_steps("", 0) == []
    assert ",".join(step["kind"] for step in grab_release_steps("gosh-toggle", 0)) == "allow-none"
    dropped = grab_entries_to_drop([(7, {"name": "keep"}), (8, {"name": "old"})], 7)
    assert [entry["name"] for entry in dropped] == ["old"]


def test_run_grab_release_still_ungrabs_after_allow_throws() -> None:
    calls: list[str] = []

    def allow_none(name: str) -> None:
        calls.append(f"allow:{name}")
        message = "allow"
        raise RuntimeError(message)

    def ungrab(action: int) -> None:
        calls.append(f"ungrab:{action}")

    released = run_grab_release(grab_release_steps("gosh-toggle", 9), {"allowNone": allow_none, "ungrab": ungrab})
    assert ",".join(calls) == "allow:gosh-toggle,ungrab:9"
    assert released == 1


def test_shortcut_hold_repeat_is_ignored() -> None:
    assert should_ignore_shortcut_repeat(1000, 0) is False
    assert should_ignore_shortcut_repeat(10_000, 1_000) is True
    assert should_ignore_shortcut_repeat(80_000, 1_000) is False
    # stamp the ignored event so a held key stays suppressed
    stamped = 10_000
    assert should_ignore_shortcut_repeat(stamped + 30_000, stamped) is True
