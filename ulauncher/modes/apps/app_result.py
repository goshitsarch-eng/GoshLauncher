from __future__ import annotations

from os.path import basename
from typing import Any, Literal

from ulauncher.internals.result import Result
from ulauncher.modes.apps.app_rankings import AppRankings
from ulauncher.utils.desktop_app import DesktopApp

ACTION_PREFIX = "action:"


def _desktop_method(app_info: Any, method: str) -> Any | None:
    getter = getattr(app_info, method, None)
    return getter if callable(getter) else None


def _desktop_actions(app_info: Any) -> dict[str, dict[Literal["name", "icon"], str]]:
    # goshos appInfo.js: list_actions is desktop-only. GNOME 50 can type some
    # get_installed() entries as GAppInfo, so the method is missing not null.
    # A throwing action list must not drop the app row.
    actions: dict[str, dict[Literal["name", "icon"], str]] = {"launch": {"name": "Launch application"}}
    list_actions = _desktop_method(app_info, "list_actions")
    if list_actions is None:
        return actions
    try:
        ids = list_actions() or []
    except Exception:  # noqa: BLE001
        return actions
    get_action_name = _desktop_method(app_info, "get_action_name")
    for action_name in ids:
        display_name = action_name
        if get_action_name is not None:
            try:
                display_name = get_action_name(action_name) or action_name
            except Exception:  # noqa: BLE001, S112
                continue
        if display_name:
            actions[f"{ACTION_PREFIX}{action_name}"] = {"name": str(display_name)}
    return actions


def _desktop_text(app_info: Any, method: str) -> str:
    getter = _desktop_method(app_info, method)
    if getter is None:
        return ""
    try:
        return str(getter() or "")
    except Exception:  # noqa: BLE001
        return ""


def _desktop_keywords(app_info: Any) -> list[str]:
    getter = _desktop_method(app_info, "get_keywords")
    if getter is None:
        return []
    try:
        keywords = getter()
    except Exception:  # noqa: BLE001
        return []
    if isinstance(keywords, (list, tuple)):
        return [str(item) for item in keywords]
    return []


class AppResult(Result):
    searchable: bool = True
    app_id: str = ""
    generic_name: str = ""
    keywords: list[str] = []
    _executable: str = ""
    # goshos Shell.App.can_open_new_window() is false for these while running
    single_window: bool = False

    def __init__(self, app_info: DesktopApp) -> None:
        super().__init__(
            name=app_info.get_display_name(),
            icon=app_info.get_string("Icon") or "",
            # Comment only. GenericName is a separate phrase so "browser" can
            # match Firefox without treating Comment as a haystack.
            description=app_info.get_description() or "",
            actions=_desktop_actions(app_info),
        )
        self.generic_name = _desktop_text(app_info, "get_generic_name")
        self.keywords = _desktop_keywords(app_info)
        self.app_id = app_info.get_id() or ""
        # TryExec is what we actually want (name of/path to exec), but it's often not specified
        # get_executable uses Exec, which is always specified, but it will return the actual executable.
        # Sometimes the actual executable is not the app to start, but a wrappers like "env" or "sh -c"
        self._executable = basename(app_info.get_string("TryExec") or app_info.get_executable() or "")
        self.single_window = bool(
            app_info.get_boolean("X-GNOME-SingleWindow") or app_info.get_boolean("SingleMainWindow")
        )

    @staticmethod
    def from_id(app_id: str) -> AppResult | None:
        # Uninstalled ids, invalid encoding, and missing desktop-only methods
        # must not hide the rest of an empty-state or rankings list.
        try:
            app_info = DesktopApp.new(app_id)
            if app_info:
                return AppResult(app_info)
        except Exception:  # noqa: BLE001
            return None
        return None

    def get_searchable_fields(self) -> list[tuple[str, float]]:
        frequency_weight = 1.0
        sorted_app_ids = AppRankings.load().get_app_ids()
        if count := len(sorted_app_ids):
            index = sorted_app_ids.index(self.app_id) if self.app_id in sorted_app_ids else count
            frequency_weight = 1.0 - (index / count * 0.1) + 0.05

        return [
            (self.name, 1 * frequency_weight),
            (self._executable, 0.8 * frequency_weight),  # command names, such as "baobab" or "nautilus"
            (self.generic_name, 0.7 * frequency_weight),
            (self.description, 0.7 * frequency_weight),
            *[(k, 0.6 * frequency_weight) for k in self.keywords],
        ]
