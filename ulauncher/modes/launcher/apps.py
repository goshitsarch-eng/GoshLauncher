"""Application matching using Spotlight-goshos word rules on desktop entries."""

from __future__ import annotations

from ulauncher.modes.apps.app_mode import AppMode
from ulauncher.modes.apps.app_result import AppResult
from ulauncher.modes.launcher.word_match import (
    id_matches_query,
    keyword_matches_query,
    label_matches_query,
    text_matches_all_words,
    text_matches_query,
)

_app_mode = AppMode()


def iter_apps() -> list[AppResult]:
    return list(_app_mode.get_triggers())


def app_matches(app: AppResult, query: str) -> bool:
    if not query:
        return False
    if text_matches_query(app.name, query) or text_matches_all_words(app.name, query):
        return True
    if label_matches_query(app.description, query):
        return True
    if any(keyword_matches_query(keyword, query) for keyword in app.keywords):
        return True
    if id_matches_query(app.app_id.replace(".desktop", "").replace("-", " "), query):
        return True
    return bool(app._executable and text_matches_query(app._executable, query))  # noqa: SLF001


def match_score(app: AppResult, query: str) -> float:
    q = query.lower()
    name = app.name.lower()
    score = 0.0
    if name.startswith(q):
        score += 100
    elif text_matches_query(app.name, query):
        score += 70
    if text_matches_all_words(app.name, query):
        score += 20
    if any(keyword_matches_query(keyword, query) for keyword in app.keywords):
        score += 15
    if label_matches_query(app.description, query):
        score += 10
    for field, weight in app.get_searchable_fields():
        if field:
            score += weight
    return score


def collapse_variants(apps: list[AppResult]) -> list[AppResult]:
    seen: dict[str, AppResult] = {}
    order: list[str] = []
    for app in apps:
        key = app.name.split()[0].lower() if app.name else app.app_id
        if key not in seen:
            seen[key] = app
            order.append(key)
        elif match_score(app, app.name) > match_score(seen[key], seen[key].name):
            seen[key] = app
    return [seen[key] for key in order]


def match_apps(query: str, limit: int = 6) -> list[AppResult]:
    ranked = sorted(
        (app for app in iter_apps() if app_matches(app, query)),
        key=lambda app: match_score(app, query),
        reverse=True,
    )
    return collapse_variants(ranked)[:limit]


def home_apps(limit: int) -> list[AppResult]:
    return _app_mode.get_home_results(limit)
