#!/usr/bin/env python3
"""Instantiate both windows using the installed Qt/Kirigami runtime.

Run on a KDE development host or the Fedora CI job. This catches invalid QML
properties and signal handlers that Python-only unit tests cannot detect.
"""

# ruff: noqa: SLF001 -- integration check inspects the instantiated QML roots
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, qInstallMessageHandler

from ulauncher.ui.app import UlauncherApp  # noqa: TID251
from ulauncher.ui.launcher_window import LauncherWindow  # noqa: TID251
from ulauncher.ui.preferences.prefs_window import PreferencesWindow, PrefsBackend  # noqa: TID251
from ulauncher.utils.settings import Settings


def main() -> None:
    errors: list[str] = []

    def message_handler(_kind: object, _context: object, message: str) -> None:
        if any(term in message for term in ("ReferenceError", "TypeError", "Cannot assign", "is not defined")):
            errors.append(message)

    extension = {
        "id": "smoke",
        "name": "Smoke extension",
        "authors": "Test",
        "updated": "",
        "enabled": True,
        "icon": "",
        "error": "",
        "instructions": "",
        "manageable": True,
        "has_update_url": False,
        "url": "",
        "status": "on",
        "triggers": [{"id": "run", "name": "Run", "keyword": "smoke"}],
        "prefs": [
            {
                "id": "notes",
                "name": "Notes",
                "description": "Multiline setting",
                "type": "text",
                "value": "Line one\nLine two",
                "options": [],
                "min": 0,
                "max": 100,
            }
        ],
    }
    qInstallMessageHandler(message_handler)
    with patch.object(Settings, "load", return_value=Settings()), patch.object(
        PrefsBackend, "extensions", return_value=[extension]
    ), patch.object(PrefsBackend, "shortcuts", return_value=[]):
        app = UlauncherApp()
        launcher = LauncherWindow(app)
        prefs = PreferencesWindow(app)
        detail = prefs._window.findChild(QObject, "extensionDetail")
        if detail is None:
            msg = "Extension editor was not instantiated"
            raise RuntimeError(msg)
        detail.setProperty("ext", extension)
        prefs._window.setProperty("visible", True)
        app.qt_app.processEvents()
        # Loading extension controls must also work after switching pages.
        for page in ("extensions", "about", "general"):
            prefs.show(page)
            app.qt_app.processEvents()
        launcher._window.setProperty("visible", True)
        app.qt_app.processEvents()
        if errors:
            raise RuntimeError("\n".join(errors))
        launcher.hide()
        prefs._window.setProperty("visible", False)
    qInstallMessageHandler(None)


if __name__ == "__main__":
    main()
