"""Decide which providers a query should run, ported from spotlight-goshos searchPlan.js."""

from __future__ import annotations

import re
from typing import Any

from ulauncher.modes.launcher.prefix import parse_query

PREFIX_TO_FLAG = {
    "calculator": "calculator",
    "web": "web",
    "settings": "settings",
    "windows": "windows",
    "files": "files",
    "command": "command",
}

DEFAULT_ORDER = [
    "url",
    "path",
    "places",
    "bookmarks",
    "apps",
    "calculator",
    "units",
    "color",
    "time",
    "windows",
    "system",
    "settings",
    "files",
]
WINDOWS_FIRST_ORDER = [
    "url",
    "path",
    "places",
    "bookmarks",
    "windows",
    "apps",
    "calculator",
    "units",
    "color",
    "time",
    "system",
    "settings",
    "files",
]
STRIP_VERB_MODES = {"all", "windows", "settings", "files"}

POLITE_PREFIX = re.compile(
    r"^(please|can\s+you|could\s+you|would\s+you|will\s+you|tell\s+me|help\s+me|just|i\s+want\s+to)\s+",
    re.IGNORECASE,
)
LAUNCH_VERB = re.compile(
    r"^(open\s+up|start\s+up|fire\s+up|open|launch|run|start|show|find|search(?:\s+for)?|"
    r"look(?:\s+up|\s+for|up)|switch\s+to|go\s+to|navigate\s+to|focus|convert|calculate|"
    r"compute|execute|what(?:['’]s|s|\s+is)|how\s+much\s+is)\s+(.+)$",
    re.IGNORECASE,
)
KEEP_OPEN_NAME = re.compile(r"^(source|office|vpn|jdk)\b", re.IGNORECASE)
LEADING_ARTICLE = re.compile(r"^(?:my|the|an?|me)\s+(.+)$", re.IGNORECASE)
CATEGORY_PREFIX = re.compile(
    r"^(windows?|settings?|files?|recent(?:\s+files?)?|apps?|applications?)\s+(.+)$", re.IGNORECASE
)
TRAILING_NOUN = re.compile(
    r"^(.+)\s+(folders?|directories|directory|dirs?|settings?|preferences|prefs)$", re.IGNORECASE
)
PATH_QUERY = re.compile(r"^(~(?:/.*)?|\.(?:/.*)?|\.\.(?:/.*)?|/.*)$")


def flags_from_settings(settings: Any) -> dict[str, Any]:
    return {
        "prefix_modes": settings.enable_prefix_modes,
        "url": settings.enable_url_open,
        "path": settings.enable_path_open,
        "places": settings.enable_places,
        "bookmarks": settings.enable_bookmarks,
        "apps": settings.enable_application_mode,
        "calculator": settings.enable_calculator,
        "units": settings.enable_unit_convert,
        "color": settings.enable_color_hex,
        "time": settings.enable_time_date,
        "windows": settings.enable_window_search,
        "system": settings.enable_system_actions,
        "settings": settings.enable_settings_search,
        "files": settings.enable_recent_files,
        "command": settings.enable_command_run,
        "web": settings.show_web_search,
        "result_order": settings.result_order,
    }


def is_path_query(query: str) -> bool:
    text = query.strip()
    if not text:
        return False
    if text == "~" or text.startswith("~/"):
        return True
    if text == "." or text.startswith("./"):
        return True
    if text == ".." or text.startswith("../"):
        return True
    return text.startswith("/")


def should_refresh_recent_files(enable_files: bool, plan: dict[str, Any]) -> bool:
    if not enable_files:
        return False
    if plan.get("mode") == "files":
        return True
    return plan.get("mode") == "all" and "files" in plan.get("providers", [])


def should_refresh_path(enable_path: bool, plan: dict[str, Any]) -> bool:
    if not enable_path:
        return False
    return "path" in plan.get("providers", []) and is_path_query(plan.get("query") or "")


def should_refresh_command(enable_command: bool, plan: dict[str, Any]) -> bool:
    if not enable_command:
        return False
    return plan.get("mode") == "command" and "command" in plan.get("providers", [])


def should_refresh_bookmarks(enable_bookmarks: bool, plan: dict[str, Any]) -> bool:
    if not enable_bookmarks:
        return False
    return plan.get("mode") == "all" and "bookmarks" in plan.get("providers", [])


def should_refresh_windows(enable_windows: bool, enable_apps: bool, plan: dict[str, Any]) -> bool:
    providers = plan.get("providers") or []
    if enable_windows and "windows" in providers:
        return True
    return bool(enable_apps and "apps" in providers)


def is_active_search_query(query: str) -> bool:
    return bool(query.strip())


def strip_polite_prefixes(query: str) -> str:
    text = query
    nxt = POLITE_PREFIX.sub("", text)
    while nxt != text:
        text = nxt.strip()
        nxt = POLITE_PREFIX.sub("", text)
    return text


def strip_one_article(query: str) -> str:
    match = LEADING_ARTICLE.match(query)
    if not match:
        return query
    rest = match.group(1).strip()
    return rest or query


def strip_leading_articles(query: str) -> str:
    text = query
    nxt = strip_one_article(text)
    while nxt != text:
        text = nxt
        nxt = strip_one_article(text)
    return text


def strip_one_prefix(query: str, pattern: re.Pattern[str]) -> str:
    match = pattern.match(query)
    if not match:
        return query
    rest = match.group(2).strip()
    return rest or query


def strip_trailing_noun(query: str) -> str:
    match = TRAILING_NOUN.match(query)
    if not match:
        return query
    rest = match.group(1).strip()
    return rest or query


def strip_answer_to(query: str) -> str:
    match = re.match(r"^(?:the\s+)?answer\s+to\s+(.+)$", query, re.IGNORECASE)
    if not match:
        return query
    rest = match.group(1).strip()
    return rest or query


def strip_leading_verb(query: str) -> str:
    text = strip_polite_prefixes(query.strip())
    match = LAUNCH_VERB.match(text)
    if match:
        rest = match.group(2).strip()
        if rest and not (match.group(1).lower() == "open" and KEEP_OPEN_NAME.search(rest)):
            without_up = re.sub(r"^up\s+", "", rest, flags=re.IGNORECASE)
            text = without_up or rest
    text = strip_leading_articles(text)
    text = strip_answer_to(text)
    text = strip_one_prefix(text, CATEGORY_PREFIX)
    return strip_trailing_noun(text)


def plan_search(text: str, flags: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_query(text) if flags.get("prefix_modes") else {"mode": "all", "query": text.strip()}
    query = strip_leading_verb(parsed["query"]) if parsed["mode"] in STRIP_VERB_MODES else parsed["query"]

    if parsed["mode"] == "all" and not is_active_search_query(query):
        return {"mode": "all", "query": "", "providers": [], "web_fallback": False}

    if parsed["mode"] != "all":
        if parsed["mode"] == "web":
            return {"mode": "web", "query": query, "providers": ["web"], "web_fallback": False}
        flag = PREFIX_TO_FLAG[parsed["mode"]]
        return {
            "mode": parsed["mode"],
            "query": query,
            "providers": [parsed["mode"]] if flags.get(flag) else [],
            "web_fallback": False,
        }

    order = WINDOWS_FIRST_ORDER if flags.get("result_order") == "windows-first" else DEFAULT_ORDER
    providers = [name for name in order if flags.get(name)]
    return {"mode": "all", "query": query, "providers": providers, "web_fallback": bool(flags.get("web"))}


def merge_empty_suggestions(result_order: str, windows: list[Any], apps: list[Any], max_results: int) -> list[Any]:
    if max_results <= 0:
        return []
    primary = windows if result_order == "windows-first" else apps
    secondary = apps if result_order == "windows-first" else windows
    results: list[Any] = []
    for row in [*primary, *secondary]:
        if len(results) >= max_results:
            break
        results.append(row)
    return results
