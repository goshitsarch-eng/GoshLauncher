"""GNOME Settings panel catalog."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from ulauncher.modes.launcher.word_match import keyword_matches_query, word_prefix_match


class SettingsPanel(TypedDict):
    id: str
    title: str
    icon: str
    keywords: list[str]


SETTINGS_PANELS: list[SettingsPanel] = [
    {
        "id": "wifi",
        "title": "Wi-Fi",
        "icon": "network-wireless-symbolic",
        "keywords": ["wireless", "wlan", "hotspot", "airplane"],
    },
    {"id": "network", "title": "Network", "icon": "network-wired-symbolic", "keywords": ["ethernet", "vpn"]},
    {"id": "wwan", "title": "Mobile Network", "icon": "network-cellular-symbolic", "keywords": ["cellular", "lte"]},
    {"id": "bluetooth", "title": "Bluetooth", "icon": "bluetooth-symbolic", "keywords": ["bt"]},
    {
        "id": "display",
        "title": "Displays",
        "icon": "video-display-symbolic",
        "keywords": ["monitor", "resolution", "night light", "scale", "fractional scaling"],
    },
    {"id": "sound", "title": "Sound", "icon": "audio-speakers-symbolic", "keywords": ["audio", "volume", "speaker"]},
    {
        "id": "power",
        "title": "Power",
        "icon": "battery-symbolic",
        "keywords": ["battery", "sleep", "battery saver", "lid"],
    },
    {
        "id": "multitasking",
        "title": "Multitasking",
        "icon": "view-app-grid-symbolic",
        "keywords": ["workspaces", "overview"],
    },
    {
        "id": "background",
        "title": "Appearance",
        "icon": "preferences-desktop-wallpaper-symbolic",
        "keywords": ["theme", "dark", "style", "wallpaper", "background", "appearance"],
    },
    {
        "id": "notifications",
        "title": "Notifications",
        "icon": "preferences-system-notifications-symbolic",
        "keywords": ["do not disturb", "dnd"],
    },
    {"id": "search", "title": "Search", "icon": "system-search-symbolic", "keywords": []},
    {
        "id": "applications",
        "title": "Applications",
        "icon": "view-grid-symbolic",
        "keywords": ["apps", "default apps", "defaults"],
    },
    {
        "id": "privacy",
        "title": "Privacy & Security",
        "icon": "preferences-system-privacy-symbolic",
        "keywords": [
            "permissions",
            "camera",
            "webcam",
            "microphone",
            "location",
            "gps",
            "thunderbolt",
            "bolt",
            "diagnostics",
            "crash",
            "firmware",
            "lock",
            "screen lock",
            "device security",
        ],
    },
    {"id": "online-accounts", "title": "Online Accounts", "icon": "emblem-web-symbolic", "keywords": ["goa", "google"]},
    {"id": "sharing", "title": "Sharing", "icon": "folder-publicshare-symbolic", "keywords": ["remote"]},
    {
        "id": "wellbeing",
        "title": "Wellbeing",
        "icon": "face-smile-symbolic",
        "keywords": ["screentime", "screen time", "limit", "break"],
    },
    {"id": "keyboard", "title": "Keyboard", "icon": "input-keyboard-symbolic", "keywords": ["shortcut", "input"]},
    {"id": "mouse", "title": "Mouse & Touchpad", "icon": "input-mouse-symbolic", "keywords": ["trackpad", "pointer"]},
    {"id": "wacom", "title": "Drawing Tablet", "icon": "input-tablet-symbolic", "keywords": ["stylus", "pen", "wacom"]},
    {"id": "color", "title": "Color", "icon": "color-select-symbolic", "keywords": ["icc", "calibration"]},
    {"id": "printers", "title": "Printers", "icon": "printer-symbolic", "keywords": ["cups"]},
    {
        "id": "universal-access",
        "title": "Accessibility",
        "icon": "preferences-desktop-accessibility-symbolic",
        "keywords": ["a11y", "screen reader", "zoom", "magnifier", "large text", "contrast", "hearing"],
    },
    {
        "id": "users",
        "title": "Users",
        "icon": "system-users-symbolic",
        "keywords": ["account", "password", "user-accounts"],
    },
    {
        "id": "region",
        "title": "Region & Language",
        "icon": "preferences-desktop-locale-symbolic",
        "keywords": ["locale", "timezone"],
    },
    {"id": "datetime", "title": "Date & Time", "icon": "preferences-system-time-symbolic", "keywords": ["clock"]},
    {
        "id": "about",
        "title": "About",
        "icon": "dialog-information-symbolic",
        "keywords": ["hardware", "version", "info-overview", "winver"],
    },
    {
        "id": "system",
        "title": "System",
        "icon": "preferences-system-symbolic",
        "keywords": [
            "software update",
            "software updates",
            "remote desktop",
            "ssh",
            "secure shell",
            "firmware",
            "device security",
            "secure boot",
        ],
    },
]


def settings_argv(panel_id: str, find_in_path: Callable[[str], str | None] | None = None) -> list[str] | None:
    panel_id = "background" if panel_id == "appearance" else panel_id
    locate = find_in_path
    if locate is None:
        from ulauncher.modes.launcher.gio_launch import find_in_user_path

        locate = find_in_user_path
    if locate("gnome-control-center"):
        return ["gnome-control-center", panel_id]
    if locate("gio"):
        return ["gio", "launch", f"gnome-{panel_id}-panel.desktop"]
    if locate("gapplication"):
        return ["gapplication", "launch", "org.gnome.Settings", panel_id]
    return None


def settings_result_meta(panel: SettingsPanel, argv: list[str] | None) -> dict:
    return {
        "type": "settings",
        "title": panel["title"],
        "description": "GNOME Settings",
        "icon": panel.get("icon") or "preferences-system-symbolic",
        "id": panel["id"],
        "activatable": argv is not None,
    }


def settings_panel_desktop(panel_id: str) -> str:
    panel_id = "background" if panel_id == "appearance" else panel_id
    return f"gnome-{panel_id}-panel.desktop"


def _desktop_exists(desktop_id: str) -> bool:
    dirs = os.environ.get("XDG_DATA_DIRS", "/usr/share:/usr/local/share").split(":")
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    return any(Path(directory, "applications", desktop_id).is_file() for directory in [home, *dirs])


def settings_panel_available(panel_id: str, has_desktop: Callable[[str], bool] | None = None) -> bool:
    if panel_id != "wellbeing":
        return True
    checker = has_desktop or _desktop_exists
    try:
        return bool(checker(settings_panel_desktop(panel_id)))
    except Exception:
        return True


def match_settings_panels(
    query: str, limit: int = 6, is_available: Callable[[str], bool] | None = None
) -> list[SettingsPanel]:
    # goshos matchSettingsPanels: omitted isAvailable lists the whole catalog,
    # including wellbeing. Live search passes settings_panel_available.
    catalog = (
        SETTINGS_PANELS if is_available is None else [panel for panel in SETTINGS_PANELS if is_available(panel["id"])]
    )
    lower = query.lower()
    normalized = lower.replace("-", "").replace("_", "").replace(" ", "")
    if not normalized:
        return catalog[:limit]
    matches: list[SettingsPanel] = []
    for panel in catalog:
        title_lower = panel["title"].lower()
        normalized_title = title_lower.replace("-", "").replace("_", "").replace(" ", "")
        normalized_id = panel["id"].replace("-", "").replace("_", "")
        hit = (
            normalized_title.startswith(normalized)
            or normalized_id.startswith(normalized)
            or title_lower.startswith(lower)
            or word_prefix_match(title_lower, lower)
            or any(keyword_matches_query(keyword, lower) for keyword in panel["keywords"])
        )
        if hit:
            matches.append(panel)
        if len(matches) >= limit:
            break
    return matches
