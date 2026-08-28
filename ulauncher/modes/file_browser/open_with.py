from __future__ import annotations

import logging
from pathlib import Path

from ulauncher.internals.result import Result
from ulauncher.utils.desktop_app import DesktopApp
from ulauncher.utils.mime_apps import content_type_of, recommended_apps_for

logger = logging.getLogger(__name__)


class OpenWithAppResult(Result):
    compact: bool = True
    path: str = ""
    app_id: str = ""
    actions = {"open_with_app": {"name": "Open with this application", "icon": "system-run"}}


def get_open_with_results(path: str) -> list[Result]:
    """Build a result for each application that can open the file at the given path."""
    results: list[Result] = []
    for app in recommended_apps_for(content_type_of(path)):
        app_id = app.get_id()
        if not app_id:
            continue
        results.append(
            OpenWithAppResult(
                name=app.get_display_name(),
                icon=app.get_string("Icon") or "",
                path=path,
                app_id=app_id,
            )
        )
    if not results:
        unsupported_msg = "No application is registered to handle this file type"
        return [Result(name=unsupported_msg, compact=True, icon="dialog-information")]
    return results


def open_path_with_app(app_id: str, path: str) -> bool:
    app = DesktopApp.new(app_id)
    if not app:
        logger.error("Could not load app %s to open %s", app_id, path)
        return False
    uri = Path(path).absolute().as_uri()
    if not app.launch_uris([uri]):
        logger.error("Could not open %s with app %s", uri, app_id)
        return False
    return True
