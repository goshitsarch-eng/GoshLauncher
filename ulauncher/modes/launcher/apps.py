"""Application matching using Spotlight-goshos word rules on desktop entries."""

from __future__ import annotations

import re
from typing import Any

from ulauncher.modes.apps.app_mode import AppMode
from ulauncher.modes.apps.app_result import AppResult
from ulauncher.modes.launcher.word_match import (
    SUBSTRING_MIN,
    id_matches_query,
    keyword_matches_query,
    label_matches_query,
    word_prefix_match,
)

_app_mode = AppMode()
_VARIANT_SUFFIX = re.compile(r"[\s-]+(esr|beta|nightly|dev|canary|stable|preview)$", re.IGNORECASE)


def iter_apps() -> list[AppResult]:
    return list(_app_mode.get_triggers())


def app_base_name(name: str) -> str:
    return _VARIANT_SUFFIX.sub("", name.lower()).strip()


def unique_by_base_name(apps: list[Any], limit: int) -> list[Any]:
    if limit <= 0:
        return []
    seen: set[str] = set()
    unique: list[Any] = []
    for app in apps:
        base = app_base_name(getattr(app, "name", "") or getattr(app, "app_id", ""))
        if base in seen:
            continue
        seen.add(base)
        unique.append(app)
        if len(unique) >= limit:
            break
    return unique


def _token_tier(name_lower: str, generic_lower: str, id_lower: str, keywords: list[str], desc_lower: str, token: str) -> int:
    if name_lower.startswith(token):
        return 0
    if word_prefix_match(name_lower, token):
        return 1
    if len(token) >= SUBSTRING_MIN and token in name_lower:
        return 2
    if label_matches_query(generic_lower, token):
        return 3
    if id_matches_query(id_lower, token):
        return 4
    if any(keyword_matches_query(keyword, token) for keyword in keywords):
        return 5
    if len(token) >= SUBSTRING_MIN and label_matches_query(desc_lower, token):
        return 6
    return -1


def app_match_tier(app: Any, query: str) -> int:
    if not query:
        return -1
    q = query.lower()
    name_lower = str(getattr(app, "name", "")).lower()
    generic_lower = str(getattr(app, "description", "")).lower()
    id_raw = str(getattr(app, "app_id", "")).lower()
    id_lower = id_raw[:-8] if id_raw.endswith(".desktop") else id_raw
    keywords = list(getattr(app, "keywords", []) or [])
    desc_lower = generic_lower

    if name_lower.startswith(q):
        return 0
    if word_prefix_match(name_lower, q):
        return 1
    if len(q) >= SUBSTRING_MIN and q in name_lower:
        return 2
    if label_matches_query(generic_lower, q):
        return 3
    if id_matches_query(id_lower, q):
        return 4
    if any(keyword_matches_query(keyword, q) for keyword in keywords):
        return 5
    if len(q) >= SUBSTRING_MIN and label_matches_query(desc_lower, q):
        return 6

    words = [word for word in q.split() if word]
    if len(words) < 2:
        return -1
    worst = 0
    for word in words:
        tier = _token_tier(name_lower, generic_lower, id_lower, keywords, desc_lower, word)
        if tier < 0:
            return -1
        worst = max(worst, tier)
    return 7 + worst


def app_matches(app: AppResult, query: str) -> bool:
    return app_match_tier(app, query) >= 0


def match_apps(query: str, limit: int = 6) -> list[AppResult]:
    ranked = sorted(
        (app for app in iter_apps() if app_match_tier(app, query) >= 0),
        key=lambda app: app_match_tier(app, query),
    )
    return unique_by_base_name(ranked, limit)


def home_apps(limit: int) -> list[AppResult]:
    return _app_mode.get_home_results(limit)
