"""GNOME Settings panel catalog."""

from __future__ import annotations

import shutil

from ulauncher.modes.launcher.word_match import keyword_matches_query, word_prefix_match

SETTINGS_PANELS = [
    {
        "id": "wifi",
        "title": "Wi-Fi",
        "icon": "network-wireless",
        "keywords": ["wireless", "wlan", "hotspot", "airplane"],
    },
    {"id": "network", "title": "Network", "icon": "network-wired", "keywords": ["ethernet", "vpn"]},
    {"id": "wwan", "title": "Mobile Network", "icon": "network-cellular", "keywords": ["cellular", "lte"]},
    {"id": "bluetooth", "title": "Bluetooth", "icon": "bluetooth", "keywords": ["bt"]},
    {
        "id": "display",
        "title": "Displays",
        "icon": "video-display",
        "keywords": ["monitor", "resolution", "night light", "scale", "fractional scaling"],
    },
    {"id": "sound", "title": "Sound", "icon": "audio-speakers", "keywords": ["audio", "volume", "speaker"]},
    {"id": "power", "title": "Power", "icon": "battery", "keywords": ["battery", "sleep", "battery saver", "lid"]},
    {"id": "multitasking", "title": "Multitasking", "icon": "view-app-grid", "keywords": ["workspaces", "overview"]},
    {
        "id": "background",
        "title": "Appearance",
        "icon": "preferences-desktop-wallpaper",
        "keywords": ["theme", "dark", "style", "wallpaper", "background", "appearance"],
    },
    {
        "id": "notifications",
        "title": "Notifications",
        "icon": "preferences-system-notifications",
        "keywords": ["do not disturb", "dnd"],
    },
    {"id": "search", "title": "Search", "icon": "system-search", "keywords": []},
    {
        "id": "applications",
        "title": "Applications",
        "icon": "view-grid",
        "keywords": ["apps", "default apps", "defaults"],
    },
    {
        "id": "privacy",
        "title": "Privacy & Security",
        "icon": "preferences-system-privacy",
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
    {"id": "online-accounts", "title": "Online Accounts", "icon": "emblem-web", "keywords": ["goa", "google"]},
    {"id": "sharing", "title": "Sharing", "icon": "folder-publicshare", "keywords": ["remote"]},
    {
        "id": "wellbeing",
        "title": "Wellbeing",
        "icon": "face-smile",
        "keywords": ["screentime", "screen time", "limit", "break"],
    },
    {"id": "keyboard", "title": "Keyboard", "icon": "input-keyboard", "keywords": ["shortcut", "input"]},
    {"id": "mouse", "title": "Mouse & Touchpad", "icon": "input-mouse", "keywords": ["trackpad", "pointer"]},
    {"id": "wacom", "title": "Drawing Tablet", "icon": "input-tablet", "keywords": ["stylus", "pen", "wacom"]},
    {"id": "color", "title": "Color", "icon": "color-select", "keywords": ["icc", "calibration"]},
    {"id": "printers", "title": "Printers", "icon": "printer", "keywords": ["cups"]},
    {
        "id": "universal-access",
        "title": "Accessibility",
        "icon": "preferences-desktop-accessibility",
        "keywords": ["a11y", "screen reader", "zoom", "magnifier", "large text", "contrast", "hearing"],
    },
    {"id": "users", "title": "Users", "icon": "system-users", "keywords": ["account", "password", "user-accounts"]},
    {
        "id": "region",
        "title": "Region & Language",
        "icon": "preferences-desktop-locale",
        "keywords": ["locale", "timezone"],
    },
    {"id": "datetime", "title": "Date & Time", "icon": "preferences-system-time", "keywords": ["clock"]},
    {
        "id": "about",
        "title": "About",
        "icon": "dialog-information",
        "keywords": ["hardware", "version", "info-overview", "winver"],
    },
    {
        "id": "system",
        "title": "System",
        "icon": "preferences-system",
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


def settings_argv(panel_id: str) -> list[str] | None:
    panel_id = "background" if panel_id == "appearance" else panel_id
    if shutil.which("gnome-control-center"):
        return ["gnome-control-center", panel_id]
    if shutil.which("gio"):
        return ["gio", "launch", f"gnome-{panel_id}-panel.desktop"]
    if shutil.which("gapplication"):
        return ["gapplication", "launch", "org.gnome.Settings", panel_id]
    return None


def match_settings_panels(query: str, limit: int = 6) -> list[dict]:
    lower = query.lower()
    normalized = lower.replace("-", "").replace("_", "").replace(" ", "")
    matches: list[dict] = []
    for panel in SETTINGS_PANELS:
        title_lower = panel["title"].lower()
        normalized_title = title_lower.replace("-", "").replace("_", "").replace(" ", "")
        normalized_id = panel["id"].replace("-", "").replace("_", "")
        hit = False
        if (
            not normalized
            or normalized_title.startswith(normalized)
            or normalized_id.startswith(normalized)
            or title_lower.startswith(lower)
            or word_prefix_match(title_lower, lower)
        ):
            hit = True
        else:
            hit = any(keyword_matches_query(keyword, lower) for keyword in panel["keywords"])
        if hit:
            matches.append(panel)
        if len(matches) >= limit:
            break
    return matches
