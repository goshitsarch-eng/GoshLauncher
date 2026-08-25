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
        "commands": [
            ["gsettings", "set", "org.gnome.settings-daemon.peripherals.touchscreen", "orientation-lock", "true"]
        ],
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
    title = action["title"].lower()
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
        from ulauncher.gi import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        for method in ("CanPowerOff", "CanReboot", "CanSuspend"):
            result = bus.call_sync(
                "org.freedesktop.login1",
                "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager",
                method,
                None,
                GLib.VariantType.new("(s)"),
                Gio.DBusCallFlags.NONE,
                150,
                None,
            )
            answers[method] = str(result.unpack()[0])
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


def match_system_actions(query: str, limit: int = 6, can_map: dict[str, str] | None = None) -> list[SystemAction]:
    answers = can_map if can_map is not None else probe_logind()
    results: list[SystemAction] = []
    for action in SYSTEM_ACTIONS:
        if not action_is_available(action["id"], answers):
            continue
        if action_matches(action, query):
            results.append(action)
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
        from ulauncher.gi import Gio, GLib
    except (ImportError, AttributeError, RuntimeError, OSError):
        return False
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            "Screenshot",
            GLib.Variant("(sa{sv})", ("", {"interactive": GLib.Variant("b", True)})),
            None,
            Gio.DBusCallFlags.NONE,
            400,
            None,
        )
        return True
    except Exception:
        return False


def run_system_action(action_id: str, screenshot_ui: Callable[[], bool] | None = None) -> None:
    if action_id == "screenshot":
        show = screenshot_ui if screenshot_ui is not None else show_screenshot_ui
        if show():
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
