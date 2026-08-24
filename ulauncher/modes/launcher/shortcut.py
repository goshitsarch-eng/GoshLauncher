"""Hotkey grab policy, ported from Spotlight-goshos shortcutAccel.js."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

DEFAULT_FALLBACK = "<Control>space"
CAPTURE_PROMPT = "Press a key combination..."

MODIFIER_KEY_NAMES = frozenset(
    {
        "Control_L",
        "Control_R",
        "Shift_L",
        "Shift_R",
        "Alt_L",
        "Alt_R",
        "Super_L",
        "Super_R",
        "Meta_L",
        "Meta_R",
        "Hyper_L",
        "Hyper_R",
        "Caps_Lock",
        "ISO_Level3_Shift",
        "ISO_Level5_Shift",
    }
)


def is_modifier_key_name(key_name: str) -> bool:
    return key_name in MODIFIER_KEY_NAMES


def normalize_accel_key(key_name: str | None) -> str:
    if not key_name:
        return ""
    if len(key_name) == 1:
        return key_name.lower()
    return key_name


def modifiers_from_mask(state: int, masks: Mapping[str, int]) -> dict[str, bool]:
    return {
        "super": bool(state & masks["super"]),
        "control": bool(state & masks["control"]),
        "shift": bool(state & masks["shift"]),
        "alt": bool(state & masks["alt"]),
        "meta": bool(state & masks["meta"]),
    }


def build_accelerator(key_name: str, mods: Mapping[str, bool]) -> str:
    key = normalize_accel_key(key_name)
    if not key:
        return ""
    accelerator = ""
    if mods.get("super"):
        accelerator += "<Super>"
    if mods.get("control"):
        accelerator += "<Control>"
    if mods.get("shift"):
        accelerator += "<Shift>"
    if mods.get("alt"):
        accelerator += "<Alt>"
    # super also sets meta on most keyboards so do not write both
    if mods.get("meta") and not mods.get("super"):
        accelerator += "<Meta>"
    return accelerator + key


def format_accelerator(accelerator: str | None) -> str:
    if not accelerator:
        return ""
    return (
        accelerator.replace("<Super>", "Super+")
        .replace("<Control>", "Ctrl+")
        .replace("<Shift>", "Shift+")
        .replace("<Alt>", "Alt+")
        .replace("<Meta>", "Meta+")
    )


def format_shortcut_list(shortcut_array: list[str] | None) -> str:
    if not shortcut_array:
        return ""
    return format_accelerator(shortcut_array[0])


def shortcut_display_label(shortcut_array: list[str] | None) -> str:
    return format_shortcut_list(shortcut_array) or "Not set (will default to Ctrl+Space)"


def shortcut_label_after_change(shortcut_array: list[str] | None, capturing: bool) -> str | None:
    if capturing:
        return None
    return shortcut_display_label(shortcut_array)


def shortcut_row_label(shortcut_array: list[str] | None, capturing: bool) -> str:
    """Prompt while capturing; settings writes must not overwrite that prompt."""
    after = shortcut_label_after_change(shortcut_array, capturing)
    if after is None:
        return CAPTURE_PROMPT
    return after


def next_shortcut_capture_action(capturing: bool, kind: str) -> str:
    """goshos shortcutPage.js: click to capture, Tab-away / Escape restore, key commits."""
    if kind == "activate":
        return "start"
    if not capturing:
        return "ignore"
    if kind in {"focus-out", "escape"}:
        return "cancel"
    if kind == "modifier":
        return "keep"
    if kind == "commit":
        return "commit"
    return "keep"


def shortcut_capture_key_kind(key_name: str | None) -> str:
    if key_name == "Escape":
        return "escape"
    if not key_name or is_modifier_key_name(key_name):
        return "modifier"
    return "commit"


def accelerator_grab_flags(flags: Mapping[str, int] | None) -> int:
    if not flags:
        return 0
    ignore = flags.get("IGNORE_AUTOREPEAT")
    if isinstance(ignore, int) and ignore > 0:
        return ignore
    return 0


def should_ignore_shortcut_repeat(now_us: int, last_time_us: int, min_gap_us: int = 0) -> bool:
    """Hold-repeat must not cancel a pending open or flip reopen-after-close.

    Mutter grabs use IGNORE_AUTOREPEAT. Portal and GApplication activations can
    still repeat. Stamp last_time on ignored events too so a held key stays quiet.
    """
    from ulauncher.modes.launcher.nav_repeat import NAV_REPEAT_GAP_US

    gap = min_gap_us if min_gap_us > 0 else NAV_REPEAT_GAP_US
    if last_time_us <= 0:
        return False
    return now_us - last_time_us < gap


def grab_release_steps(name: str, action: int) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if name:
        steps.append({"kind": "allow-none", "name": name})
    if action:
        steps.append({"kind": "ungrab", "action": action})
    return steps


def grab_entries_to_drop(entries: Iterable[tuple[Any, Any]], keep_action: int) -> list[dict[str, Any]]:
    dropped: list[dict[str, Any]] = []
    for action, grabber in entries:
        ident = int(action)
        if ident == keep_action:
            continue
        dropped.append(
            {
                "action": ident,
                "name": grabber.get("name") if isinstance(grabber, dict) else getattr(grabber, "name", "") or "",
            }
        )
    return dropped


def run_grab_release(steps: Iterable[Mapping[str, Any]], handlers: Mapping[str, Callable[..., Any]]) -> int:
    released = 0
    for step in steps:
        try:
            if step["kind"] == "allow-none":
                handlers["allowNone"](step["name"])
            elif step["kind"] == "ungrab":
                handlers["ungrab"](step["action"])
            released += 1
        except Exception:  # noqa: S110
            pass
    return released


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
