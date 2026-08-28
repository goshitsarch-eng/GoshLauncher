"""System power and session actions."""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Mapping
from typing import Any, Callable, TypedDict

from ulauncher.modes.launcher.word_match import keyword_matches_query, word_prefix_match
from ulauncher.utils.launch_detached import launch_detached

logger = logging.getLogger(__name__)

STOP_WORDS = re.compile(r"\b(the|a|an|my|please|computer|system|session|machine|pc|of|now)\b", re.IGNORECASE)


class SystemAction(TypedDict):
    id: str
    title: str
    icon: str
    keywords: list[str]
    commands: list[list[str]]


def screenshot_commands() -> list[list[str]]:
    # Goshos opens Screenshot.showScreenshotUI(); a GTK app launches the same UI.
    return [
        ["gtk-launch", "org.gnome.Screenshot"],
        ["gtk-launch", "org.gnome.Snapshot"],
        ["gnome-screenshot", "-i"],
        ["gnome-screenshot"],
        ["grim"],
    ]


SYSTEM_ACTIONS: list[SystemAction] = [
    {
        "id": "lock",
        "title": "Lock Screen",
        "icon": "system-lock-screen-symbolic",
        "keywords": ["lock", "lockscreen", "lock screen", "lock the screen", "lock now"],
        "commands": [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "-l"],
        ],
    },
    {
        "id": "logout",
        "title": "Log Out",
        "icon": "system-log-out-symbolic",
        "keywords": ["logout", "signout", "log out", "sign out", "log off", "sign off"],
        "commands": [
            ["gnome-session-quit", "--logout", "--no-prompt"],
            ["loginctl", "terminate-session", ""],
        ],
    },
    {
        "id": "suspend",
        "title": "Suspend",
        "icon": "media-playback-pause-symbolic",
        "keywords": ["suspend", "sleep"],
        "commands": [["systemctl", "suspend"], ["loginctl", "suspend"]],
    },
    {
        "id": "restart",
        "title": "Restart",
        "icon": "system-reboot-symbolic",
        "keywords": ["restart", "reboot"],
        "commands": [["systemctl", "reboot"], ["gnome-session-quit", "--reboot", "--no-prompt"]],
    },
    {
        "id": "shutdown",
        "title": "Power Off",
        "icon": "system-shutdown-symbolic",
        "keywords": ["shutdown", "shut down", "poweroff", "power off", "turn off", "halt", "shut down the computer"],
        "commands": [["systemctl", "poweroff"], ["gnome-session-quit", "--power-off", "--no-prompt"]],
    },
    {
        "id": "switch-user",
        "title": "Switch User",
        "icon": "system-switch-user-symbolic",
        "keywords": ["switch user", "switchuser"],
        "commands": [["gdmflexiserver"], ["dm-tool", "switch-to-greeter"]],
    },
    {
        "id": "lock-orientation",
        "title": "Lock Screen Rotation",
        "icon": "rotation-locked-symbolic",
        "keywords": [
            "rotation",
            "orientation",
            "rotate",
            "unlock",
            "lock orientation",
            "unlock orientation",
            "unlock rotation",
        ],
        "commands": [],
    },
    {
        "id": "screenshot",
        "title": "Take a Screenshot",
        "icon": "record-screen-symbolic",
        "keywords": ["screenshot", "snip", "capture", "screencast", "record"],
        "commands": screenshot_commands(),
    },
]


def normalize_action_query(query: str) -> str:
    text = STOP_WORDS.sub(" ", query.lower())
    return re.sub(r"\s+", " ", text).strip()


def action_matches(action: Mapping[str, Any], query: str) -> bool:
    q = normalize_action_query(query)
    if not q:
        return False
    # The query has its stop words stripped, so the title needs the same treatment or an action
    # cannot be found by its own name: "take a screenshot" normalizes to "take screenshot",
    # which matched neither "take a screenshot" nor any keyword.
    title = normalize_action_query(action["title"])
    if title.startswith(q) or word_prefix_match(title, q):
        return True
    return any(keyword_matches_query(keyword, q) for keyword in action["keywords"])


_LOGIND_CAN = {
    "shutdown": "CanPowerOff",
    "restart": "CanReboot",
    "suspend": "CanSuspend",
}


class _LogindState:
    cache: dict[str, str] | None = None


_logind = _LogindState()


def probe_logind(*, force: bool = False) -> dict[str, str]:
    if _logind.cache is not None and not force:
        return _logind.cache
    answers: dict[str, str] = {}
    try:
        from ulauncher.utils import qdbus

        bus = qdbus.system_bus()
        for method in ("CanPowerOff", "CanReboot", "CanSuspend"):
            result = qdbus.call(
                bus,
                "org.freedesktop.login1",
                "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager",
                method,
                timeout_ms=150,
            )
            if result:
                answers[method] = str(result[0])
    except Exception:
        logger.debug("logind Can* probe failed", exc_info=True)
    _logind.cache = answers
    return answers


def action_is_available(action_id: str, can_map: dict[str, str] | None = None) -> bool:
    if action_id == "screenshot":
        return True
    method = _LOGIND_CAN.get(action_id)
    if method is None:
        return True
    answer = (can_map if can_map is not None else probe_logind()).get(method)
    if answer is None:
        return True
    return str(answer).lower() not in {"no", "na"}


ORIENTATION_SCHEMA = "org.gnome.settings-daemon.peripherals.touchscreen"
ORIENTATION_KEY = "orientation-lock"


def get_orientation_locked() -> bool:
    import subprocess

    exe = shutil.which("gsettings")
    if not exe:
        return False
    try:
        raw = subprocess.check_output(
            [exe, "get", ORIENTATION_SCHEMA, ORIENTATION_KEY], text=True, stderr=subprocess.DEVNULL, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return raw.strip() == "true"


def set_orientation_locked(locked: bool) -> bool:
    exe = shutil.which("gsettings")
    if not exe:
        return False
    launch_detached([exe, "set", ORIENTATION_SCHEMA, ORIENTATION_KEY, "true" if locked else "false"])
    return True


def toggle_orientation_lock() -> bool:
    return set_orientation_locked(not get_orientation_locked())


def orientation_title(locked: bool) -> str:
    return "Unlock Screen Rotation" if locked else "Lock Screen Rotation"


def orientation_icon(locked: bool) -> str:
    return "rotation-locked-symbolic" if locked else "rotation-allowed-symbolic"


def match_system_actions(
    query: str,
    limit: int = 6,
    can_map: dict[str, str] | None = None,
    orientation_locked: bool | None = None,
) -> list[SystemAction]:
    answers = can_map if can_map is not None else probe_logind()
    locked = get_orientation_locked() if orientation_locked is None else orientation_locked
    results: list[SystemAction] = []
    for action in SYSTEM_ACTIONS:
        if not action_is_available(action["id"], answers):
            continue
        if not action_matches(action, query):
            continue
        locked_title = action["id"] == "lock-orientation"
        results.append(
            {
                "id": action["id"],
                "title": orientation_title(locked) if locked_title else action["title"],
                "icon": orientation_icon(locked) if locked_title else action["icon"],
                "keywords": action["keywords"],
                "commands": action["commands"],
            }
        )
        if len(results) >= limit:
            break
    return results


def show_screenshot_ui(bus_call: Callable[[], bool] | None = None) -> bool:
    """Open the GNOME screenshot UI (goshos Screenshot.showScreenshotUI).

    A GTK app cannot import gnome-shell's screenshot.js. The session portal
    interactive Screenshot request is the public equivalent.
    """
    call = bus_call or _portal_screenshot_call
    return bool(call())


def _portal_screenshot_call() -> bool:
    try:
        from ulauncher.utils import qdbus

        reply = qdbus.call(
            qdbus.session_bus(),
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            "Screenshot",
            ["", {"interactive": True}],
            timeout_ms=400,
        )
        return reply is not None
    except Exception:
        return False


def run_system_action(action_id: str, screenshot_ui: Callable[[], bool] | None = None) -> None:
    if action_id == "screenshot":
        show = screenshot_ui if screenshot_ui is not None else show_screenshot_ui
        if show():
            return
    if action_id == "lock-orientation":
        if not toggle_orientation_lock():
            logger.warning("No working command for system action %s", action_id)
        return
    for action in SYSTEM_ACTIONS:
        if action["id"] != action_id:
            continue
        for cmd in action["commands"]:
            if cmd[0] and not shutil.which(cmd[0]):
                continue
            try:
                launch_detached(cmd)
                return
            except Exception:
                logger.debug("System action %s failed for %s", action_id, cmd, exc_info=True)
        logger.warning("No working command for system action %s", action_id)
        return
