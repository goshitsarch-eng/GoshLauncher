from __future__ import annotations

import logging
from typing import Any, Callable, Iterator, Sequence

from ulauncher.internals import effects
from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.modes.launcher.looks import chrome_from_settings
from ulauncher.modes.launcher.plan import flags_from_settings, merge_empty_suggestions, plan_search
from ulauncher.modes.launcher.results import LauncherResult, SectionHeader
from ulauncher.modes.mode import Mode
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings

_events: EventBus = EventBus()
logger = logging.getLogger()


class LauncherMode(Mode):
    """Spotlight-style search: URLs, paths, apps, calc, units, color, clock, windows, settings, recents, web."""

    def matches_query_str(self, query_str: str) -> bool:
        return bool(query_str)

    def handle_query(self, query: Query, callback: Callable[[effects.EffectMessage], None]) -> None:
        settings = Settings.load()
        flags = flags_from_settings(settings)
        chrome = chrome_from_settings(settings)
        if flags.get("result_order") in (None, "", "default"):
            flags["result_order"] = chrome.get("result_order") or "default"
        planned = plan_search(str(query), flags)
        callback(effects.render_results(self._results_for_plan(planned, settings, chrome)))

    def get_home_results(self, limit: int) -> Sequence[Result]:
        settings = Settings.load()
        if not getattr(settings, "enable_empty_suggestions", True) or limit <= 0:
            return []
        from ulauncher.modes.launcher.apps import app_row_description, app_window_count, home_apps
        from ulauncher.modes.launcher.windows import list_windows

        chrome = chrome_from_settings(settings)
        flags = flags_from_settings(settings)
        order = flags.get("result_order") or chrome.get("result_order") or "default"
        if order == "default":
            order = chrome.get("result_order") or "default"
        app_limit = min(limit, max(1, int(getattr(settings, "max_recent_apps", 6) or 6)))
        open_windows = list_windows() if flags.get("windows") or flags.get("apps") else []
        app_rows: list[dict[str, Any]] = []
        if flags.get("apps"):
            for app in home_apps(app_limit):
                app_rows.append(
                    {
                        "kind": "app",
                        "title": app.name,
                        "description": app_row_description(app_window_count(app, open_windows)),
                        "icon": app.icon,
                        "app_id": app.app_id,
                    }
                )
        win_rows: list[dict[str, Any]] = []
        if flags.get("windows"):
            for win in open_windows:
                if win.sticky or win.desktop < 0:
                    workspace = "On all workspaces"
                else:
                    workspace = f"Workspace {win.desktop + 1}"
                win_rows.append(
                    {
                        "kind": "window",
                        "title": win.title or win.wm_class,
                        "description": workspace,
                        "icon": "focus-windows",
                        "wid": win.wid,
                        "pid": win.pid,
                        "wm_class": win.wm_class,
                        "window_kind": "focus",
                    }
                )
        merged = merge_empty_suggestions(order, win_rows, app_rows, limit)
        return list(self._materialize(merged, chrome, headers=False))

    def activate_result(
        self,
        action_id: str,
        result: Result,
        query: Query,  # noqa: ARG002
        callback: Callable[[effects.EffectMessage], None],
    ) -> None:
        if not isinstance(result, LauncherResult):
            callback(effects.do_nothing())
            return
        kind = result.kind
        payload = result.payload if isinstance(result.payload, dict) else {}
        if kind == "app":
            from ulauncher.modes.apps.app_rankings import AppRankings
            from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
            from ulauncher.modes.apps.launch_app import launch_app

            app_id = str(payload.get("app_id") or "")
            if not app_id or not AppResult.from_id(app_id):
                callback(effects.do_nothing())
                return
            action_name = payload.get("action_name")
            launched = False
            if action_id.startswith(ACTION_PREFIX):
                launched = launch_app(app_id, action_name=action_id[len(ACTION_PREFIX) :])
            elif action_name:
                launched = launch_app(app_id, action_name=str(action_name))
            else:
                launched = launch_app(app_id)
            if launched:
                AppRankings.load().bump(app_id)
                callback(effects.close_window())
                return
            callback(effects.do_nothing())
            return
        if kind == "url":
            from ulauncher.modes.launcher.paths import canonicalize_launch_uri

            url = canonicalize_launch_uri(str(payload.get("url") or ""))
            if not url:
                callback(effects.do_nothing())
                return
            callback(effects.open(url))
            return
        if kind == "path":
            from ulauncher.modes.launcher.paths import terminal_command
            from ulauncher.utils.launch_detached import launch_detached, open_detached

            if not payload.get("exists", True) and not payload.get("in_terminal"):
                callback(effects.do_nothing())
                return
            path = str(payload["path"])
            if payload.get("in_terminal"):
                cmd = terminal_command(path)
                if cmd:
                    launch_detached(list(cmd["argv"]), working_dir=cmd.get("cwd"))
                    callback(effects.close_window())
                    return
                callback(effects.do_nothing())
                return
            open_detached(path)
            callback(effects.close_window())
            return
        if kind in {"calculator", "units", "color", "clock"}:
            _events.emit("app:copy_and_close", str(payload.get("copy_text") or result.name))
            callback(effects.close_window())
            return
        if kind == "window":
            from ulauncher.modes.launcher.windows import activate_window

            activate_window(payload)
            callback(effects.close_window())
            return
        if kind == "settings":
            from ulauncher.modes.launcher.settings_panels import settings_argv
            from ulauncher.utils.launch_detached import launch_detached

            argv = settings_argv(str(payload["panel_id"]))
            if argv:
                launch_detached(argv)
            callback(effects.close_window())
            return
        if kind == "web":
            callback(effects.open(str(payload["url"])))
            return
        if kind == "command":
            from ulauncher.utils.launch_detached import launch_detached

            if not payload.get("ready") or not payload.get("argv"):
                callback(effects.do_nothing())
                return
            from pathlib import Path

            launch_detached(list(payload["argv"]), working_dir=str(payload.get("cwd") or Path.home()))
            callback(effects.close_window())
            return
        if kind == "system":
            from ulauncher.modes.launcher.system_actions import run_system_action

            run_system_action(str(payload["action_id"]))
            callback(effects.close_window())
            return
        callback(effects.do_nothing())

    def _results_for_plan(self, planned: dict[str, Any], settings: Settings, chrome: dict[str, Any]) -> list[Result]:
        rows = list(self._collect(planned, settings))
        show_headers = bool(chrome.get("show_headers")) and planned["mode"] == "all"
        return list(self._materialize(rows, chrome, headers=show_headers))

    def _collect(self, planned: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
        mode = planned["mode"]
        q = planned["query"]
        providers = planned["providers"]
        web_fallback = planned["web_fallback"]
        cap = max(1, int(getattr(settings, "max_per_category", 6) or 6))
        buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in providers}

        def add(name: str, row: dict[str, Any]) -> None:
            if name in buckets:
                buckets[name].append(row)

        if "url" in providers:
            from ulauncher.modes.launcher.urls import match_url

            hit = match_url(q)
            if hit:
                from ulauncher.modes.launcher.paths import canonicalize_launch_uri

                url = canonicalize_launch_uri(str(hit["url"]))
                if url:
                    add(
                        "url",
                        {
                            "kind": "url",
                            "score": 200,
                            "title": hit.get("label") or url,
                            "description": hit.get("description") or "",
                            "icon": hit.get("icon") or "web-browser",
                            "url": url,
                        },
                    )

        if "path" in providers:
            from ulauncher.modes.launcher.paths import match_path

            hit = match_path(q)
            if hit:
                from ulauncher.modes.launcher.paths import terminal_row_meta

                add(
                    "path",
                    {
                        "kind": "path",
                        "score": 190,
                        "title": hit["title"],
                        "description": hit.get("description") or "",
                        "icon": hit.get("icon") or "folder",
                        "path": hit["path"],
                        "in_terminal": False,
                        "exists": hit.get("exists", True),
                    },
                )
                if hit.get("is_dir") and hit.get("exists"):
                    term = terminal_row_meta(hit["path"])
                    add("path", {"kind": "path", "score": 189, **term})

        if "places" in providers:
            from ulauncher.modes.launcher.places import match_places

            for index, hit in enumerate(match_places(q)[:cap]):
                add(
                    "places",
                    {
                        "kind": "path",
                        "score": 80,
                        "title": hit["title"],
                        "description": hit.get("description") or "",
                        "path": hit["path"],
                        "in_terminal": False,
                    },
                )
                if index == 0:
                    from ulauncher.modes.launcher.paths import terminal_row_meta

                    term = terminal_row_meta(str(hit["path"]))
                    add("places", {"kind": "path", "score": 79, **term})

        if "bookmarks" in providers:
            from ulauncher.modes.launcher.bookmarks import match_bookmarks

            for hit in match_bookmarks(q)[:cap]:
                row = _row_from_uri(hit, score=75)
                if row:
                    add("bookmarks", row)

        if "apps" in providers:
            from ulauncher.modes.launcher.apps import app_action_rows, app_row_description, app_window_count, match_apps
            from ulauncher.modes.launcher.windows import list_windows

            matched = match_apps(q, cap)
            open_windows = list_windows()
            for app in matched:
                actions = dict(app.actions) if app.actions else {"activate": {"name": "Activate"}}
                if not getattr(settings, "enable_app_actions", True):
                    actions = (
                        {"launch": actions["launch"]} if "launch" in actions else {"activate": {"name": "Activate"}}
                    )
                window_count = app_window_count(app, open_windows)
                add(
                    "apps",
                    {
                        "kind": "app",
                        "score": 70,
                        "title": app.name,
                        "description": app_row_description(window_count),
                        "icon": app.icon,
                        "app_id": app.app_id,
                        "actions": actions,
                    },
                )
            if matched and getattr(settings, "enable_app_actions", True):
                for action in app_action_rows(matched[0], cap, app_window_count(matched[0], open_windows)):
                    add(
                        "apps",
                        {
                            "kind": "app",
                            "score": 69,
                            "title": action["title"],
                            "description": action["description"],
                            "icon": action.get("icon") or "application-x-executable",
                            "app_id": action["app_id"],
                            "action_name": action["action_name"],
                            "actions": {"activate": {"name": "Activate"}},
                        },
                    )

        if "calculator" in providers:
            from ulauncher.modes.launcher.calculator import calculator_description, evaluate_arithmetic, format_number

            value = evaluate_arithmetic(q, allow_bare=(mode == "calculator"))
            if value is not None:
                formatted = format_number(value)
                add(
                    "calculator",
                    {
                        "kind": "calculator",
                        "score": 95,
                        "title": formatted,
                        "description": calculator_description(value),
                        "copy_text": formatted,
                    },
                )

        if "units" in providers:
            from ulauncher.modes.launcher.units import convert_query

            hit = convert_query(q)
            if hit:
                add(
                    "units",
                    {
                        "kind": "units",
                        "score": 90,
                        "title": hit["title"],
                        "description": hit["description"],
                        "copy_text": hit["copy_text"],
                    },
                )

        if "color" in providers:
            from ulauncher.modes.launcher.color import parse_color, rgb_to_hsl

            hit = parse_color(q)
            if hit:
                hue, sat, light = rgb_to_hsl(int(hit["r"]), int(hit["g"]), int(hit["b"]))
                add(
                    "color",
                    {
                        "kind": "color",
                        "score": 85,
                        "title": hit["hex"],
                        "description": f"rgb({hit['r']}, {hit['g']}, {hit['b']}) · hsl({hue}, {sat}%, {light}%)",
                        "copy_text": hit["hex"],
                    },
                )

        if "time" in providers:
            from ulauncher.modes.launcher.clock import match_clock

            hit = match_clock(q)
            if hit:
                add(
                    "time",
                    {
                        "kind": "clock",
                        "score": 60,
                        "title": hit["title"],
                        "description": hit["description"],
                        "copy_text": hit["copy_text"],
                    },
                )

        if "windows" in providers:
            from ulauncher.modes.launcher.windows import match_windows

            for win in match_windows(q, cap):
                add(
                    "windows",
                    {
                        "kind": "window",
                        "score": 65,
                        "title": win["title"],
                        "description": win.get("description") or "",
                        "icon": win.get("icon") or "focus-windows",
                        "wid": win.get("wid") or win.get("payload") or "",
                        "pid": win.get("pid") or 0,
                        "wm_class": win.get("wm_class") or "",
                        "window_kind": win.get("kind") or "focus",
                        "payload": win.get("payload"),
                    },
                )

        if "system" in providers:
            from ulauncher.modes.launcher.system_actions import match_system_actions

            for hit in match_system_actions(q)[:cap]:
                add(
                    "system",
                    {
                        "kind": "system",
                        "score": 50,
                        "title": hit["title"],
                        "description": "System",
                        "icon": hit.get("icon") or "system-shutdown",
                        "action_id": hit["id"],
                    },
                )

        if "settings" in providers:
            from ulauncher.modes.launcher.settings_panels import match_settings_panels

            for hit in match_settings_panels(q)[:cap]:
                add(
                    "settings",
                    {
                        "kind": "settings",
                        "score": 55,
                        "title": hit["title"],
                        "description": "Settings",
                        "icon": hit.get("icon") or "preferences-system",
                        "panel_id": hit["id"],
                    },
                )

        if "files" in providers:
            from ulauncher.modes.launcher.recents import match_recents

            for hit in match_recents(q)[:cap]:
                row = _row_from_uri(hit, score=45)
                if row:
                    add("files", row)

        if "command" in providers:
            from ulauncher.modes.launcher.commands import resolve_command_row

            hit = resolve_command_row(q)
            if hit:
                add(
                    "command",
                    {
                        "kind": "command",
                        "score": 40,
                        "title": hit["title"],
                        "description": hit["description"],
                        "icon": hit.get("icon") or "utilities-terminal",
                        "argv": hit.get("argv") or [],
                        "ready": bool(hit.get("ready")),
                        "cwd": hit.get("cwd"),
                    },
                )

        if "web" in providers:
            from ulauncher.modes.launcher.web import web_result

            engine_id = getattr(settings, "web_search_engine", "google")
            hit = web_result(q, engine_id)
            add(
                "web",
                {
                    "kind": "web",
                    "score": 10,
                    "title": hit["title"],
                    "description": hit.get("description") or "",
                    "icon": hit.get("icon") or "web-browser",
                    "url": hit["url"],
                },
            )

        rows = [row for name in providers for row in buckets.get(name, [])]
        if web_fallback and not rows:
            from ulauncher.modes.launcher.web import web_result

            engine_id = getattr(settings, "web_search_engine", "google")
            hit = web_result(q, engine_id)
            rows.append(
                {
                    "kind": "web",
                    "score": 10,
                    "title": hit["title"],
                    "description": hit.get("description") or "",
                    "icon": hit.get("icon") or "web-browser",
                    "url": hit["url"],
                }
            )

        return rows

    def _materialize(self, rows: Sequence[dict[str, Any]], chrome: dict[str, Any], headers: bool) -> Iterator[Result]:
        last_kind = ""
        labels = {
            "url": "Open Link",
            "path": "Folders",
            "app": "Applications",
            "calculator": "Calculator",
            "units": "Convert",
            "color": "Color",
            "clock": "Clock",
            "window": "Windows",
            "system": "System",
            "settings": "Settings",
            "web": "Search the Web",
            "command": "Run Command",
        }
        compact = chrome.get("density") == "compact"
        show_icons = chrome.get("show_result_icons", True)
        show_descriptions = chrome.get("show_descriptions", True)
        for row in rows:
            kind = str(row["kind"])
            if headers and kind != last_kind:
                yield SectionHeader(name=labels.get(kind, kind.title()), compact=True)
                last_kind = kind
            payload = {
                k: v for k, v in row.items() if k not in {"kind", "score", "title", "description", "icon", "actions"}
            }
            if kind == "window":
                payload["kind"] = row.get("window_kind") or "focus"
            icon = "" if not show_icons else str(row.get("icon") or _default_icon(kind))
            actions = row.get("actions") or {"activate": {"name": "Activate"}}
            if kind == "command" and not row.get("ready"):
                actions = {}
            if kind == "path" and not row.get("exists", True):
                actions = {}
            yield LauncherResult(
                name=str(row["title"]),
                description="" if not show_descriptions else str(row.get("description") or ""),
                icon=icon,
                compact=compact,
                kind=kind,
                payload=payload,
                highlightable=True,
                actions=actions,
            )


def _row_from_uri(hit: dict[str, Any], score: int) -> dict[str, Any] | None:
    from ulauncher.modes.launcher.paths import canonicalize_launch_uri, path_from_file_uri

    uri = canonicalize_launch_uri(str(hit.get("uri") or hit.get("path") or ""))
    if not uri:
        return None
    path = path_from_file_uri(uri)
    if path:
        return {
            "kind": "path",
            "score": score,
            "title": hit["title"],
            "description": hit.get("description") or "",
            "icon": hit.get("icon") or "folder",
            "path": path,
            "in_terminal": False,
            "exists": True,
        }
    return {
        "kind": "url",
        "score": score,
        "title": hit["title"],
        "description": hit.get("description") or "",
        "icon": hit.get("icon") or "network-server",
        "url": uri,
    }


def _default_icon(kind: str) -> str:
    return {
        "url": "web-browser",
        "path": "folder",
        "app": "application-x-executable",
        "calculator": "accessories-calculator",
        "units": "accessories-calculator",
        "color": "applications-graphics",
        "clock": "preferences-system-time",
        "window": "focus-windows",
        "system": "system-shutdown",
        "settings": "preferences-system",
        "web": "web-browser",
        "command": "utilities-terminal",
    }.get(kind, "application-x-executable")
