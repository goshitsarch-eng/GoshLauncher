"""Hold compositor unredirect while the popup is open.

Ported from Spotlight-goshos unredirect.js. Mutter's Meta.Compositor helpers are
in-process; a GTK app holds the equivalent via the mutter gsettings key or
Hyprland ``render:direct_scanout`` so a fullscreen surface cannot scanout over
the popup.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Callable, Mapping

MUTTER_SCHEMA = "org.gnome.mutter"
MUTTER_KEY = "unredirect-fullscreen-windows"
HYPR_SCANOUT_OPTION = "render:direct_scanout"
HYPR_SCANOUT_DEFAULT = "2"


def unredirect_api(has_compositor_method: bool, has_display_method: bool) -> str:
    if has_compositor_method:
        return "compositor"
    if has_display_method:
        return "display"
    return ""


def gtk_unredirect_backend(mutter_has_key: bool, hyprland: bool) -> str:
    if mutter_has_key:
        return "mutter-gsettings"
    if hyprland:
        return "hyprland"
    return ""


def next_unredirect_action(held: bool, want_held: bool, api: str) -> str:
    if not api:
        return "keep"
    if want_held and not held:
        return "hold"
    if not want_held and held:
        return "release"
    return "keep"


def hyprland_session_active(env: Mapping[str, str] | None = None, which: Callable[[str], Any] | None = None) -> bool:
    environ = env if env is not None else os.environ
    which_fn = which if which is not None else shutil.which
    return bool(environ.get("HYPRLAND_INSTANCE_SIGNATURE") and which_fn("hyprctl"))


def hyprland_getoption_argv() -> list[str]:
    return ["hyprctl", "-j", "getoption", HYPR_SCANOUT_OPTION]


def hyprland_hold_argv() -> list[str]:
    return ["hyprctl", "keyword", HYPR_SCANOUT_OPTION, "0"]


def hyprland_restore_argv(previous: str) -> list[str]:
    value = previous or HYPR_SCANOUT_DEFAULT
    return ["hyprctl", "keyword", HYPR_SCANOUT_OPTION, value]


def parse_hyprland_scanout(payload: Any) -> str:
    data: Any = payload
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode()
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return HYPR_SCANOUT_DEFAULT
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text.split()[0]
    if isinstance(data, dict):
        if "int" in data and data["int"] is not None:
            return str(data["int"])
        if "str" in data and data["str"] not in (None, ""):
            return str(data["str"])
        nested = data.get("data")
        if nested is not None:
            return str(nested)
    if data is None:
        return HYPR_SCANOUT_DEFAULT
    return str(data)


def mutter_hold_write() -> bool:
    """Disable fullscreen unredirect while the popup is mapped."""
    return False
