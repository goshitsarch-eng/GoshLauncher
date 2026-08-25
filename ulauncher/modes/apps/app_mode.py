from __future__ import annotations

import logging
from typing import Callable, Iterator

from ulauncher import app_id
from ulauncher.gi import GioUnix
from ulauncher.internals import effects
from ulauncher.internals.query import Query
from ulauncher.internals.result import Result
from ulauncher.modes.apps.app_rankings import AppRankings
from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
from ulauncher.modes.apps.launch_app import launch_app
from ulauncher.modes.mode import Mode
from ulauncher.utils.settings import Settings

logger = logging.getLogger(__name__)


def _installed_app_result(app: GioUnix.DesktopAppInfo, settings: Settings) -> AppResult | None:
    executable = app.get_executable()
    if not executable or not app.get_display_name():
        return None
    if not app.get_show_in() and not settings.disable_desktop_filters:
        return None
    # Make an exception for gnome-control-center, because all the very useful specific settings
    # like "Keyboard", "Wi-Fi", "Sound" etc have NoDisplay=true
    if app.get_nodisplay() and executable != "gnome-control-center":
        return None
    if app.get_id() == f"{app_id}.desktop":
        return None
    return AppResult(app)


class AppMode(Mode):
    def handle_query(self, _query: Query, callback: Callable[[effects.EffectMessage], None]) -> None:
        # App mode contributes search triggers but does not handle direct query-mode execution.
        callback(effects.render_results([]))

    def get_triggers(self) -> Iterator[AppResult]:
        settings = Settings.load()

        if not settings.enable_application_mode:
            return

        for app in GioUnix.DesktopAppInfo.get_all():
            try:
                result = _installed_app_result(app, settings)
            except Exception:  # noqa: BLE001, S112
                # goshos: skip a desktop file whose get_id() throws so one bad
                # encoding cannot hide the rest of the app list.
                continue
            if result is not None:
                yield result

    def get_home_results(self, limit: int) -> list[AppResult]:
        """Get the top {N} apps (by recency-weighted score) to show when the query is empty"""
        return list(filter(None, map(AppResult.from_id, AppRankings.load().get_app_ids())))[:limit]

    def activate_result(
        self,
        action_id: str,
        result: Result,
        _query: Query,
        callback: Callable[[effects.EffectMessage], None],
    ) -> None:
        if action_id == "launch" or action_id.startswith(ACTION_PREFIX):
            if not isinstance(result, AppResult):
                logger.error("Expected AppResult but got %s", type(result).__name__)
                callback(effects.do_nothing())
                return
            AppRankings.load().bump(result.app_id)
            if action_id == "launch":
                if not launch_app(result.app_id):
                    logger.error("Could not launch app %s", result.app_id)
            elif not launch_app(result.app_id, action_name=action_id[len(ACTION_PREFIX) :]):
                logger.error("Could not run action %s of app %s", action_id, result.app_id)
            callback(effects.close_window())
            return
        logger.error("Unexpected action '%s' for App mode result '%s'", action_id, result)
        callback(effects.do_nothing())
