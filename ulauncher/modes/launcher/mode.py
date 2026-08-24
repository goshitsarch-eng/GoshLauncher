from __future__ import annotations

import logging
from typing import Any, Callable, Iterator, Sequence

from ulauncher.internals import effects
from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.modes.launcher.looks import chrome_from_settings
from ulauncher.modes.launcher.plan import (
    flags_from_settings,
    merge_empty_suggestions,
    plan_search,
    should_refresh_bookmarks,
    should_refresh_command,
    should_refresh_path,
    should_refresh_recent_files,
)
from ulauncher.modes.launcher.results import LauncherResult, SectionHeader
from ulauncher.modes.launcher.search_run import safe_provider_results
from ulauncher.modes.mode import Mode
from ulauncher.utils import scheduling
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings

_events: EventBus = EventBus()
logger = logging.getLogger()


class LauncherMode(Mode):
    """Spotlight-style search: URLs, paths, apps, calc, units, color, clock, windows, settings, recents, web."""

    def __init__(self) -> None:
        super().__init__()
        self._lookup_idle: Any = None
        self._paint_callback: Callable[[effects.EffectMessage], None] | None = None
        self._paint_planned: dict[str, Any] | None = None
        self._paint_settings: Settings | None = None
        self._paint_chrome: dict[str, Any] | None = None
        self._accept_paint = False

    def matches_query_str(self, query_str: str) -> bool:
        return bool(query_str)

    def handle_query(self, query: Query, callback: Callable[[effects.EffectMessage], None]) -> None:
        from ulauncher.modes.launcher.bookmarks import bookmarks_are_ready, ensure_bookmarks
        from ulauncher.modes.launcher.commands import (
            command_is_resolved,
            command_needs_async,
            ensure_command,
            invalidate_command_lookup,
        )
        from ulauncher.modes.launcher.paths import ensure_path, invalidate_path_lookup, path_is_resolved
        from ulauncher.modes.launcher.recents import ensure_recent_files, recents_are_ready

        settings = Settings.load()
        flags = flags_from_settings(settings)
        chrome = chrome_from_settings(settings)
        if flags.get("result_order") in (None, "", "default"):
            flags["result_order"] = chrome.get("result_order") or "default"
        planned = plan_search(str(query), flags)
        self._paint_callback = callback
        self._paint_planned = planned
        self._paint_settings = settings
        self._paint_chrome = chrome
        self._accept_paint = True
        want_path = should_refresh_path(bool(flags.get("path")), planned)
        want_command = should_refresh_command(bool(flags.get("command")), planned)
        want_bookmarks = should_refresh_bookmarks(bool(flags.get("bookmarks")), planned)
        want_recents = should_refresh_recent_files(bool(flags.get("files")), planned)
        slash_command = want_command and command_needs_async(planned["query"])
        path_async = want_path and not path_is_resolved(planned["query"])
        command_async = slash_command and not command_is_resolved(planned["query"])
        bookmarks_async = want_bookmarks and not bookmarks_are_ready()
        recents_async = want_recents and not recents_are_ready()
        callback(
            effects.render_results(
                self._results_for_plan(planned, settings, chrome),
                final=not (path_async or command_async or bookmarks_async or recents_async),
            )
        )
        if want_path:
            ensure_path(planned["query"], self._schedule_repaint)
        else:
            invalidate_path_lookup()
        if slash_command:
            ensure_command(planned["query"], self._schedule_repaint)
        else:
            invalidate_command_lookup()
        if want_bookmarks:
            ensure_bookmarks(self._schedule_repaint)
        if want_recents:
            ensure_recent_files(self._schedule_repaint)

    def _schedule_repaint(self) -> None:
        from ulauncher.modes.launcher.async_paint import should_schedule_async_paint

        if not should_schedule_async_paint(bool(self._lookup_idle), self._accept_paint):
            return
        self._lookup_idle = scheduling.run_when_idle(self._run_repaint)

    def _run_repaint(self) -> None:
        from ulauncher.modes.launcher.async_paint import should_run_async_paint

        self._lookup_idle = None
        callback = self._paint_callback
        planned = self._paint_planned
        settings = self._paint_settings
        chrome = self._paint_chrome
        query_active = planned is not None and bool(planned.get("query"))
        if callback is None or planned is None or settings is None or chrome is None:
            return
        if not should_run_async_paint(query_active, self._accept_paint):
            return
        callback(effects.render_results(self._results_for_plan(planned, settings, chrome)))

    def flush_lookups(self) -> None:
        from ulauncher.modes.launcher.bookmarks import flush_bookmarks_lookup
        from ulauncher.modes.launcher.commands import flush_command_lookup
        from ulauncher.modes.launcher.paths import flush_path_lookup
        from ulauncher.modes.launcher.recents import flush_recents_lookup

        flush_path_lookup()
        flush_command_lookup()
        flush_bookmarks_lookup()
        flush_recents_lookup()
        if self._lookup_idle:
            self._lookup_idle.cancel()
            self._run_repaint()

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
        recent_cap = int(getattr(settings, "max_recent_apps", 6) or 0)
        open_windows = list_windows() if flags.get("windows") or flags.get("apps") else []
        app_rows: list[dict[str, Any]] = []
        if flags.get("apps") and recent_cap > 0:
            for app in home_apps(min(limit, recent_cap)):
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
                        "icon": "focus-windows-symbolic",
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
        if kind in {"app", "app-action"}:
            from ulauncher.modes.apps.app_rankings import AppRankings
            from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
            from ulauncher.modes.apps.launch_app import launch_app
            from ulauncher.modes.launcher.apps import focus_open_windows

            app_id = str(payload.get("app_id") or "")
            app = AppResult.from_id(app_id) if app_id else None
            if not app_id or not app:
                callback(effects.do_nothing())
                return
            action_name = payload.get("action_name")
            launched = False
            if action_id.startswith(ACTION_PREFIX):
                launched = launch_app(app_id, action_name=action_id[len(ACTION_PREFIX) :])
            elif action_name:
                launched = launch_app(app_id, action_name=str(action_name))
            elif focus_open_windows(app):
                launched = True
            else:
                launched = launch_app(app_id)
            if launched:
                AppRankings.load().bump(app_id)
                callback(effects.close_window())
                return
            callback(effects.do_nothing())
            return
        if kind in {"url", "bookmark"} and payload.get("url"):
            from ulauncher.modes.launcher.paths import canonicalize_launch_uri

            url = canonicalize_launch_uri(str(payload.get("url") or ""))
            if not url:
                callback(effects.do_nothing())
                return
            callback(effects.open(url))
            return
        if kind in {"path", "place", "file", "bookmark"}:
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
        if kind in {"calculator", "units", "unit", "color", "clock", "time"}:
            _events.emit("app:copy_and_close", str(payload.get("copy_text") or result.name))
            callback(effects.close_window())
            return
        if kind in {"window", "workspace", "window-close"}:
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
                            "icon": hit.get("icon") or "web-browser-symbolic",
                            "url": url,
                        },
                    )

        if "path" in providers:
            from ulauncher.modes.launcher.paths import search_path

            for hit in safe_provider_results(lambda: search_path(q)):
                add(
                    "path",
                    {
                        "kind": "path",
                        "score": 189 if hit.get("in_terminal") else 190,
                        "title": hit["title"],
                        "description": hit.get("description") or "",
                        "icon": hit.get("icon") or "folder-symbolic",
                        "path": hit["path"],
                        "in_terminal": bool(hit.get("in_terminal")),
                        "exists": hit.get("exists", True),
                        "checking": bool(hit.get("checking")),
                    },
                )

        if "places" in providers:
            from ulauncher.modes.launcher.places import match_places

            for index, hit in enumerate(safe_provider_results(lambda: match_places(q))[:cap]):
                add(
                    "places",
                    {
                        "kind": "place",
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
            from ulauncher.modes.launcher.bookmarks import search_bookmarks

            for hit in safe_provider_results(lambda: search_bookmarks(q, cap)):
                row = _row_from_uri(hit, score=75, kind="bookmark")
                if row:
                    add("bookmarks", row)

        if "apps" in providers:
            from ulauncher.modes.launcher.apps import app_action_rows, app_row_description, app_window_count, match_apps
            from ulauncher.modes.launcher.windows import list_windows

            matched = safe_provider_results(lambda: match_apps(q, cap))
            open_windows = safe_provider_results(list_windows)
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
                        "id": app.app_id,
                        "actions": actions,
                    },
                )
            if matched and getattr(settings, "enable_app_actions", True):
                for action in app_action_rows(matched[0], cap, app_window_count(matched[0], open_windows)):
                    add(
                        "apps",
                        {
                            "kind": "app-action",
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
                        "icon": "accessories-calculator-symbolic",
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
                        "description": f"{hit['description']} · press Enter to copy",
                        "icon": "accessories-calculator-symbolic",
                        "copy_text": hit["copy_text"],
                    },
                )

        if "color" in providers:
            from ulauncher.modes.launcher.color import parse_color

            hit = parse_color(q)
            if hit:
                add(
                    "color",
                    {
                        "kind": "color",
                        "score": 85,
                        "title": hit["hex"],
                        "description": "Press Enter to copy color",
                        "icon": "color-select-symbolic",
                        "copy_text": hit["hex"],
                    },
                )

        if "time" in providers:
            from ulauncher.modes.launcher.clock import match_clock

            hit = match_clock(q)
            if hit:
                clock_icon = (
                    "preferences-system-time-symbolic" if hit.get("kind") == "time" else "x-office-calendar-symbolic"
                )
                add(
                    "time",
                    {
                        "kind": "clock",
                        "score": 60,
                        "title": hit["title"],
                        "description": f"{hit['description']} · press Enter to copy",
                        "icon": clock_icon,
                        "copy_text": hit["copy_text"],
                    },
                )

        if "windows" in providers:
            from ulauncher.modes.launcher.windows import match_windows

            for win in safe_provider_results(lambda: match_windows(q, cap)):
                raw_kind = win.get("kind") or "focus"
                if raw_kind == "workspace":
                    row_kind = "workspace"
                elif raw_kind in {"close", "quit", "kill"}:
                    row_kind = "window-close"
                else:
                    row_kind = "window"
                add(
                    "windows",
                    {
                        "kind": row_kind,
                        "score": 65,
                        "title": win["title"],
                        "description": win.get("description") or "",
                        "icon": win.get("icon") or "focus-windows-symbolic",
                        "wid": win.get("wid") or win.get("payload") or "",
                        "pid": win.get("pid") or 0,
                        "wm_class": win.get("wm_class") or "",
                        "window_kind": raw_kind,
                        "payload": win.get("payload"),
                        "id": win.get("id"),
                    },
                )

        if "system" in providers:
            from ulauncher.modes.launcher.system_actions import match_system_actions

            for hit in safe_provider_results(lambda: match_system_actions(q))[:cap]:
                add(
                    "system",
                    {
                        "kind": "system",
                        "score": 50,
                        "title": hit["title"],
                        "description": "System",
                        "icon": hit.get("icon") or "system-shutdown-symbolic",
                        "action_id": hit["id"],
                    },
                )

        if "settings" in providers:
            from ulauncher.modes.launcher.settings_panels import match_settings_panels

            for hit in safe_provider_results(lambda: match_settings_panels(q))[:cap]:
                add(
                    "settings",
                    {
                        "kind": "settings",
                        "score": 55,
                        "title": hit["title"],
                        "description": "GNOME Settings",
                        "icon": hit.get("icon") or "preferences-system-symbolic",
                        "panel_id": hit["id"],
                    },
                )

        if "files" in providers:
            from ulauncher.modes.launcher.recents import search_recents

            for hit in safe_provider_results(lambda: search_recents(q, cap)):
                row = _row_from_uri(hit, score=45, kind="file")
                if row:
                    add("files", row)

        if "command" in providers:
            from ulauncher.modes.launcher.commands import search_command

            for hit in safe_provider_results(lambda: search_command(q)):
                add(
                    "command",
                    {
                        "kind": "command",
                        "score": 40,
                        "title": hit["title"],
                        "description": hit["description"],
                        "icon": hit.get("icon") or "utilities-terminal-symbolic",
                        "argv": hit.get("argv") or [],
                        "ready": bool(hit.get("ready")),
                        "checking": bool(hit.get("checking")),
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
                    "icon": hit.get("icon") or "web-browser-symbolic",
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
                    "icon": hit.get("icon") or "web-browser-symbolic",
                    "url": hit["url"],
                }
            )

        return rows

    def _materialize(self, rows: Sequence[dict[str, Any]], chrome: dict[str, Any], headers: bool) -> Iterator[Result]:
        from ulauncher.modes.launcher.section_titles import section_title

        last_kind = ""
        compact = chrome.get("density") == "compact"
        show_icons = chrome.get("show_result_icons", True)
        show_descriptions = chrome.get("show_descriptions", True)
        for row in rows:
            kind = str(row["kind"])
            if headers and kind != last_kind:
                yield SectionHeader(name=section_title(kind), compact=True)
                last_kind = kind
            payload = {
                k: v for k, v in row.items() if k not in {"kind", "score", "title", "description", "icon", "actions"}
            }
            if kind in {"window", "workspace", "window-close"}:
                payload["kind"] = row.get("window_kind") or "focus"
            icon = "" if not show_icons else str(row.get("icon") or _default_icon(kind))
            actions = row.get("actions") or {"activate": {"name": "Activate"}}
            if kind == "command" and not row.get("ready"):
                actions = {}
            if kind in {"path", "place", "file", "bookmark"} and not row.get("exists", True):
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


def _row_from_uri(hit: dict[str, Any], score: int, kind: str | None = None) -> dict[str, Any] | None:
    from ulauncher.modes.launcher.paths import canonicalize_launch_uri, path_from_file_uri

    uri = canonicalize_launch_uri(str(hit.get("uri") or hit.get("path") or ""))
    if not uri:
        return None
    path = path_from_file_uri(uri)
    if path:
        return {
            "kind": kind or "path",
            "score": score,
            "title": hit["title"],
            "description": hit.get("description") or "",
            "icon": hit.get("icon") or "folder-symbolic",
            "path": path,
            "in_terminal": False,
            "exists": True,
        }
    return {
        "kind": kind or "url",
        "score": score,
        "title": hit["title"],
        "description": hit.get("description") or "",
        "icon": hit.get("icon") or "network-server-symbolic",
        "url": uri,
    }


def _default_icon(kind: str) -> str:
    return {
        "url": "web-browser-symbolic",
        "path": "folder-symbolic",
        "app": "application-x-executable-symbolic",
        "calculator": "accessories-calculator-symbolic",
        "units": "accessories-calculator-symbolic",
        "color": "color-select-symbolic",
        "clock": "preferences-system-time-symbolic",
        "window": "focus-windows-symbolic",
        "system": "system-shutdown-symbolic",
        "settings": "preferences-system-symbolic",
        "web": "web-browser-symbolic",
        "command": "utilities-terminal-symbolic",
        "place": "folder-symbolic",
        "file": "text-x-generic-symbolic",
        "bookmark": "user-bookmarks-symbolic",
        "app-action": "application-x-executable-symbolic",
        "workspace": "workspace-switcher-symbolic",
        "window-close": "window-close-symbolic",
    }.get(kind, "application-x-executable-symbolic")
