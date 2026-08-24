"""Hotkey grab policy, ported from Spotlight-goshos shortcutAccel.js."""

from __future__ import annotations

DEFAULT_FALLBACK = "<Control>space"


def shortcut_attempts(requested: str, fallback: str = DEFAULT_FALLBACK) -> list[str]:
    extras = [fallback, "<Super>space", "<Alt>space"]
    out: list[str] = []
    seen: set[str] = set()
    for accel in [requested, *extras]:
        if not accel or accel in seen:
            continue
        seen.add(accel)
        out.append(accel)
    return out or [fallback]


def shortcut_retry_list(requested: str, current_grab: str) -> list[str]:
    # a working grab must not be replaced by a fallback the user did not pick
    if current_grab:
        return []
    return [accel for accel in shortcut_attempts(requested) if accel != requested]


def shortcut_to_persist(requested: str, working: str | None) -> str | None:
    if not working or working == requested:
        return None
    return working


def hotkey_to_restore_after_failed_grab(grab_ok: bool, previous: str) -> str | None:
    if grab_ok or not previous:
        return None
    return previous
