"""Application matching using Spotlight-goshos word rules on desktop entries."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from ulauncher.modes.apps.app_mode import AppMode
from ulauncher.modes.apps.app_rankings import AppRankings
from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
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
    from ulauncher.modes.launcher.parental import app_is_allowed

    return [app for app in _app_mode.get_triggers() if app_is_allowed(app)]


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


def _token_tier(
    name_lower: str, generic_lower: str, id_lower: str, keywords: list[str], desc_lower: str, token: str
) -> int:
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
    generic_lower = str(getattr(app, "generic_name", "") or "").lower()
    id_raw = str(getattr(app, "app_id", "")).lower()
    id_lower = id_raw[:-8] if id_raw.endswith(".desktop") else id_raw
    keywords = list(getattr(app, "keywords", []) or [])
    desc_lower = str(getattr(app, "description", "") or "").lower()

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


def _usage_rank(app_id: str) -> int:
    ids = AppRankings.load().get_app_ids()
    try:
        return ids.index(app_id)
    except ValueError:
        return len(ids) + 1


def match_apps(query: str, limit: int = 6) -> list[AppResult]:
    scored: list[tuple[int, int, AppResult]] = []
    for app in iter_apps():
        try:
            tier = app_match_tier(app, query)
        except Exception:  # noqa: S112
            continue
        if tier < 0:
            continue
        scored.append((tier, _usage_rank(getattr(app, "app_id", "")), app))
    scored.sort(key=lambda item: (item[0], item[1]))
    return unique_by_base_name([app for _tier, _rank, app in scored], limit)


def app_row_description(window_count: int) -> str:
    if window_count > 0:
        return "Switch to application"
    return "Application"


def _app_class_needles(app: Any) -> set[str]:
    needles: set[str] = set()
    app_id = str(getattr(app, "app_id", "") or "").lower()
    if app_id.endswith(".desktop"):
        app_id = app_id[:-8]
    if app_id:
        needles.add(app_id)
        needles.add(app_id.split(".")[-1])
    executable = str(getattr(app, "_executable", "") or "").lower()
    if executable:
        needles.add(executable)
    return {needle for needle in needles if needle and needle != "desktop"}


def focus_open_windows(app: Any, windows: list[Any] | None = None) -> bool:
    from ulauncher.modes.launcher.windows import activate_window, list_windows

    open_windows = list_windows() if windows is None else windows
    if app_window_count(app, open_windows) <= 0:
        return False
    needles = _app_class_needles(app)
    for win in open_windows:
        cls = str(getattr(win, "wm_class", "") or "").lower()
        tokens = {part for part in re.split(r"[./]", cls) if part}
        if needles & tokens:
            activate_window(
                {
                    "kind": "focus",
                    "wid": getattr(win, "wid", ""),
                    "pid": getattr(win, "pid", 0),
                    "payload": getattr(win, "wid", ""),
                }
            )
            return True
    return False


def app_window_count(app: Any, windows: Sequence[Any] | None = None) -> int:
    if windows is None:
        from ulauncher.modes.launcher.windows import list_windows

        windows = list_windows()
    needles = _app_class_needles(app)
    if not needles:
        return 0
    count = 0
    for win in windows:
        cls = str(getattr(win, "wm_class", "") or "").lower()
        tokens = {part for part in re.split(r"[./]", cls) if part}
        if needles & tokens:
            count += 1
    return count


def home_apps(limit: int) -> list[AppResult]:
    # goshos searchFrequentApps: all usable apps, AppUsage order, then
    # takeUniqueByBaseName. Rankings-only lists hid unused apps and kept
    # Firefox plus Firefox ESR as two empty-state rows.
    ranked = AppRankings.load().get_app_ids()
    rank_index = {app_id: index for index, app_id in enumerate(ranked)}
    fallback = len(rank_index)
    usable: list[tuple[int, int, AppResult]] = []
    for index, app in enumerate(iter_apps()):
        try:
            app_id = str(getattr(app, "app_id", "") or "")
        except Exception:  # noqa: S112
            continue
        if not app_id:
            continue
        usable.append((rank_index.get(app_id, fallback), index, app))
    usable.sort(key=lambda item: (item[0], item[1]))
    return unique_by_base_name([app for _rank, _index, app in usable], limit)


def is_new_window_action(action_id: str) -> bool:
    normalized = action_id.lower().replace("_", "-")
    return normalized in {"new-window", "newwindow"}


def new_window_title(app_name: str) -> str:
    return f"New window — {app_name}"


def desktop_action_title(action_name: str, app_name: str) -> str:
    return f"{action_name} — {app_name}"


def action_result_limit(max_results: int, _used_app_rows: int) -> int:
    return max_results


def take_app_actions(actions: list[Any], max_results: int) -> list[Any]:
    if max_results <= 0:
        return []
    return actions[:max_results]


def app_action_rows(app: Any, limit: int, window_count: int = 0) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for key, meta in (getattr(app, "actions", None) or {}).items():
        if key == "launch" or not str(key).startswith(ACTION_PREFIX):
            continue
        action_id = str(key)[len(ACTION_PREFIX) :]
        if is_new_window_action(action_id) and window_count <= 0:
            continue
        name = (meta or {}).get("name") or action_id
        title = new_window_title(app.name) if is_new_window_action(action_id) else desktop_action_title(name, app.name)
        rows.append(
            {
                "title": title,
                "description": "Application action",
                "icon": getattr(app, "icon", "") or "application-x-executable",
                "app_id": getattr(app, "app_id", ""),
                "action_name": action_id,
            }
        )
        if len(rows) >= limit:
            break
    return take_app_actions(rows, limit)
