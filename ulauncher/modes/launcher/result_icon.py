"""Pick a result icon without passing a null gicon.

Ported from Spotlight-goshos resultIcon.js.
"""

from __future__ import annotations

from typing import Any


def app_icon_or_fallback(app: Any, fallback_name: str) -> dict[str, Any]:
    get_icon = getattr(app, "get_icon", None) if app is not None else None
    gicon = None
    if callable(get_icon):
        try:
            gicon = get_icon()
        except Exception:
            gicon = None
    if gicon:
        return {"gicon": gicon}
    return {"icon_name": fallback_name}


def window_icon_or_fallback(gicon: Any) -> Any:
    if gicon:
        return gicon
    return "focus-windows-symbolic"


def should_build_result_icon(show_icons: bool) -> bool:
    return bool(show_icons)


def result_icon_source(result: Any) -> dict[str, Any]:
    app = result.get("app") if isinstance(result, dict) else getattr(result, "app", None)
    if app:
        return app_icon_or_fallback(app, "application-x-executable")
    icon = result.get("icon") if isinstance(result, dict) else getattr(result, "icon", None)
    if isinstance(icon, str) and icon:
        return {"icon_name": icon}
    if icon:
        return {"gicon": icon}
    return {"icon_name": "application-x-executable-symbolic"}
