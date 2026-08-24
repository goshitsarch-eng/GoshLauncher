"""Read desktop fields that only some app infos expose, from goshos appInfo.js."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Iterable

from ulauncher.modes.launcher.apps import app_match_tier


def _call(app: Any, method: str, *args: Any) -> Any:
    getter = getattr(app, method, None)
    if not callable(getter):
        return None
    return getter(*args)


def app_id(app: Any) -> str:
    if not app:
        return ""
    value = _call(app, "get_id")
    if value:
        return str(value)
    return str(getattr(app, "app_id", "") or "")


def app_name(app: Any) -> str:
    if app:
        value = _call(app, "get_name")
        if value:
            return str(value)
        name = getattr(app, "name", None)
        if name:
            return str(name)
    return app_id(app)


def app_generic_name(app: Any) -> str:
    if not app:
        return ""
    value = _call(app, "get_generic_name")
    if value:
        return str(value)
    return str(getattr(app, "generic_name", "") or "")


def app_keywords(app: Any) -> list[str]:
    if not app:
        return []
    keywords = _call(app, "get_keywords")
    if keywords is None:
        keywords = getattr(app, "keywords", None)
    if isinstance(keywords, (list, tuple)):
        return [str(item) for item in keywords]
    return []


def app_description(app: Any) -> str:
    if not app:
        return ""
    value = _call(app, "get_description")
    if value:
        return str(value)
    return str(getattr(app, "description", "") or "")


def app_action_ids(app: Any) -> list[str]:
    if not app:
        return []
    ids = _call(app, "list_actions")
    if isinstance(ids, (list, tuple)):
        return [str(item) for item in ids]
    return []


def app_action_name(app: Any, action_id: str) -> str:
    if not app:
        return action_id
    value = _call(app, "get_action_name", action_id)
    if value:
        return str(value)
    return action_id


def describe_installed_app(app: Any) -> dict[str, Any] | None:
    identifier = app_id(app)
    if not identifier:
        return None
    return {
        "id": identifier,
        "name": app_name(app),
        "generic": app_generic_name(app),
        "keywords": app_keywords(app),
        "description": app_description(app),
    }


def collect_installed_app_matches(
    apps: Iterable[Any],
    query: str,
    should_show: Callable[[Any], bool],
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    q = (query or "").lower()
    if not q:
        return scored
    for app in apps:
        try:
            if not should_show(app):
                continue
            info = describe_installed_app(app)
            if not info:
                continue
            tier = app_match_tier(
                SimpleNamespace(
                    name=info["name"],
                    generic_name=info["generic"],
                    app_id=info["id"],
                    keywords=info["keywords"],
                    description=info["description"],
                ),
                q,
            )
            if tier < 0:
                continue
            scored.append(
                {
                    "app": app,
                    "app_id": info["id"],
                    "title": info["name"],
                    "tier": tier,
                }
            )
        except Exception:  # noqa: S112
            continue
    return scored


def collect_usable_apps(apps: Iterable[Any], should_show: Callable[[Any], bool]) -> list[Any]:
    usable: list[Any] = []
    for app in apps:
        try:
            if not should_show(app):
                continue
            if not app_id(app):
                continue
            usable.append(app)
        except Exception:  # noqa: S112
            continue
    return usable
