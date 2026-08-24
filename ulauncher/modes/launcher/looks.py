"""Launcher look catalog, ported from spotlight-goshos themes.js."""

from __future__ import annotations

from typing import Any, TypedDict


class LookChrome(TypedDict):
    position: str
    density: str
    show_numbers: bool
    show_headers: bool
    show_search_icon: bool
    show_result_icons: bool
    show_descriptions: bool
    result_order: str
    icon_size: int


class Look(TypedDict):
    id: str
    title: str
    description: str
    hint: str
    look: LookChrome


def _chrome(
    position: str = "center",
    density: str = "comfortable",
    show_numbers: bool = False,
    show_headers: bool = True,
    show_search_icon: bool = True,
    show_result_icons: bool = True,
    show_descriptions: bool = True,
    result_order: str = "default",
    icon_size: int = 28,
) -> LookChrome:
    return {
        "position": position,
        "density": density,
        "show_numbers": show_numbers,
        "show_headers": show_headers,
        "show_search_icon": show_search_icon,
        "show_result_icons": show_result_icons,
        "show_descriptions": show_descriptions,
        "result_order": result_order,
        "icon_size": icon_size,
    }


LOOKS: list[Look] = [
    {
        "id": "spotlight",
        "title": "Spotlight",
        "description": "Compact macOS-inspired pill with a separate results card",
        "hint": "Search apps...",
        "look": _chrome(icon_size=28),
    },
    {
        "id": "omarchy",
        "title": "Omarchy",
        "description": "Walker-style Tokyo Night panel used by Omarchy Linux",
        "hint": "Search...",
        "look": _chrome(icon_size=24),
    },
    {
        "id": "popos",
        "title": "Pop!_OS",
        "description": "COSMIC launcher look with windows first and number hints",
        "hint": "Type to search",
        "look": _chrome(position="top", show_numbers=True, result_order="windows-first", icon_size=36),
    },
    {
        "id": "ulauncher",
        "title": "Ulauncher",
        "description": "Alfred-like dark panel with larger icons",
        "hint": "Search",
        "look": _chrome(show_headers=False, icon_size=40),
    },
    {
        "id": "krunner",
        "title": "KRunner",
        "description": "Plasma-style compact bar with Alt+1-9 hints near the top",
        "hint": "Search or run",
        "look": _chrome(position="top", density="compact", show_numbers=True, show_headers=False, icon_size=20),
    },
    {
        "id": "gnome",
        "title": "GNOME",
        "description": "Dark Adwaita card that follows the session accent on GNOME 47+",
        "hint": "Type to search",
        "look": _chrome(icon_size=28),
    },
    {
        "id": "rofi",
        "title": "Rofi",
        "description": "dmenu-style list with the classic teal selection bar",
        "hint": "Filter",
        "look": _chrome(
            density="compact",
            show_headers=False,
            show_search_icon=False,
            show_result_icons=False,
            show_descriptions=False,
            icon_size=22,
        ),
    },
    {
        "id": "raycast",
        "title": "Raycast",
        "description": "Dark rounded panel with a red caret and no section headers",
        "hint": "Search for apps and commands...",
        "look": _chrome(show_headers=False, icon_size=32),
    },
    {
        "id": "albert",
        "title": "Albert",
        "description": "Breeze-dark card with a Plasma-blue selected row",
        "hint": "Enter a query",
        "look": _chrome(icon_size=26),
    },
    {
        "id": "wofi",
        "title": "Wofi",
        "description": "Wayland dmenu-style list with a steel-blue selected row",
        "hint": "Search",
        "look": _chrome(
            density="compact",
            show_headers=False,
            show_search_icon=False,
            show_result_icons=False,
            show_descriptions=False,
            icon_size=22,
        ),
    },
    {
        "id": "fuzzel",
        "title": "Fuzzel",
        "description": "Solarized light Wayland launcher with a 10px rounded frame",
        "hint": "Type to search",
        "look": _chrome(
            density="compact",
            show_headers=False,
            show_search_icon=False,
            show_descriptions=False,
            icon_size=24,
        ),
    },
    {
        "id": "anyrun",
        "title": "Anyrun",
        "description": "Catppuccin mocha panel used with the Anyrun Wayland launcher",
        "hint": "Search",
        "look": _chrome(show_headers=False, show_search_icon=False, show_descriptions=False, icon_size=28),
    },
    {
        "id": "tofi",
        "title": "Tofi",
        "description": "Stark dmenu-style bar used by the Tofi Wayland launcher",
        "hint": "Run",
        "look": _chrome(
            position="top",
            density="compact",
            show_headers=False,
            show_search_icon=False,
            show_result_icons=False,
            show_descriptions=False,
            icon_size=20,
        ),
    },
    {
        "id": "light",
        "title": "Light",
        "description": "Light card that follows the session accent on GNOME 47+",
        "hint": "Type to search",
        "look": _chrome(icon_size=28),
    },
    {
        "id": "powertoys",
        "title": "PowerToys",
        "description": "Windows-style runner card with Fluent blue selection and Alt+1-9 hints",
        "hint": "Type here to search",
        "look": _chrome(show_numbers=True, show_headers=False, icon_size=32),
    },
    {
        "id": "synapse",
        "title": "Synapse",
        "description": "Large-icon dark panel with an Ubuntu-orange caret",
        "hint": "Search...",
        "look": _chrome(show_headers=False, show_descriptions=False, icon_size=48),
    },
    {
        "id": "onagre",
        "title": "Onagre",
        "description": "Centered dark panel with an amber selected row",
        "hint": "Search",
        "look": _chrome(show_headers=False, show_descriptions=False, icon_size=30),
    },
]

DEFAULT_LOOK_ID = LOOKS[0]["id"]
LIGHT_LOOKS = frozenset({"light", "fuzzel"})


def look_apply_action(theme_id: str, applied_id: str) -> str:
    # goshos lookApplyAction: an empty applied-look stamps the default without
    # rewriting chrome so a custom icon size survives first enable
    if not theme_id:
        return "keep"
    if not applied_id:
        return "stamp" if theme_id == LOOKS[0]["id"] else "apply"
    if theme_id != applied_id:
        return "apply"
    return "keep"


def should_apply_look(previous_id: str, next_id: str) -> bool:
    return bool(next_id) and next_id != previous_id


def get_look(look_id: str) -> Look:
    for look in LOOKS:
        if look["id"] == look_id:
            return look
    return LOOKS[0]


def look_ids() -> list[str]:
    return [look["id"] for look in LOOKS]


def look_prefs_search_text() -> str:
    # goshos prefs/appearancePage.js: search matches the group description, not combo rows.
    # Walker / COSMIC / Dark Adwaita are aliases that must appear as those words.
    aliases = {
        "omarchy": "Omarchy (Walker)",
        "popos": "Pop!_OS (COSMIC)",
        "gnome": "GNOME (Dark Adwaita)",
    }
    names = [aliases.get(look["id"], look["title"]) for look in LOOKS]
    listed = ", ".join(names[:-1]) + f", and {names[-1]}"
    return (
        f"{listed}. A look sets colors, position, density, headers, number hints, "
        "the search icon, result icons, descriptions, icon size, and result order. "
        "You can still change those after. Width is not part of a look."
    )


def icon_size_for_look(chrome: LookChrome, density: str) -> int:
    if density == "compact":
        return round(chrome["icon_size"] * 0.8)
    return chrome["icon_size"]


def search_icon_style_class(show_search_icon: bool) -> str:
    # goshos searchIconStyleClass: the magnifier is the only left inset
    return "" if show_search_icon else "gosh-no-search-icon"


_CHROME_SETTINGS = (
    ("position", "popup_position"),
    ("density", "row_density"),
    ("show_numbers", "show_result_numbers"),
    ("show_headers", "show_section_headers"),
    ("show_search_icon", "show_search_icon"),
    ("show_result_icons", "show_result_icons"),
    ("show_descriptions", "show_descriptions"),
    ("result_order", "result_order"),
    ("icon_size", "icon_size"),
)


def look_chrome_fields(look: Look) -> dict[str, Any]:
    chrome = look["look"]
    fields: dict[str, Any] = {"applied_look": look["id"]}
    for chrome_key, settings_key in _CHROME_SETTINGS:
        fields[settings_key] = chrome[chrome_key]
    return fields


def apply_look_chrome(settings: Any, look_id: str | None = None) -> dict[str, Any]:
    """Stamp a look's chrome onto settings, matching goshos applyLookSettings."""
    look = get_look(look_id or getattr(settings, "look_id", "spotlight"))
    payload = {"look_id": look["id"], **look_chrome_fields(look)}
    save = getattr(settings, "save", None)
    if callable(save):
        save(payload)
    else:
        for key, value in payload.items():
            setattr(settings, key, value)
    return payload


def ensure_look_chrome(settings: Any) -> None:
    look = get_look(getattr(settings, "look_id", "spotlight"))
    action = look_apply_action(look["id"], str(getattr(settings, "applied_look", "") or ""))
    if action == "apply":
        apply_look_chrome(settings, look["id"])
        return
    if action == "stamp":
        save = getattr(settings, "save", None)
        if callable(save):
            save({"applied_look": look["id"]})
        else:
            settings.applied_look = look["id"]


def chrome_from_settings(settings: Any) -> LookChrome:
    look = get_look(getattr(settings, "look_id", "spotlight"))
    chrome: LookChrome = dict(look["look"])
    if getattr(settings, "applied_look", "") != look["id"]:
        return chrome
    for chrome_key, settings_key in _CHROME_SETTINGS:
        if hasattr(settings, settings_key):
            value = getattr(settings, settings_key)
            if value not in (None, ""):
                chrome[chrome_key] = value  # type: ignore[literal-required]
    return chrome
