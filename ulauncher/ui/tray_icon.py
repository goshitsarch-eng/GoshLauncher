"""System tray icon via QSystemTrayIcon (StatusNotifierItem on Linux)."""

from __future__ import annotations

import logging
import os

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ulauncher import app_display_name, paths, show_launcher_label
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings

logger = logging.getLogger(__name__)
events = EventBus()

DEFAULT_ICON_NAME = "ulauncher-indicator-symbolic"
FALLBACK_ICON_NAME = "ulauncher-indicator"


def _load_tray_icon() -> QIcon:
    for name in (Settings.load().tray_icon_name or DEFAULT_ICON_NAME, DEFAULT_ICON_NAME, FALLBACK_ICON_NAME):
        themed = QIcon.fromTheme(name)
        if not themed.isNull():
            return themed
        svg_path = os.path.join(paths.ASSETS, "icons", "system", "status", f"{name}.svg")
        if os.path.isfile(svg_path):
            return QIcon(svg_path)
    return QIcon.fromTheme("system-search")


class TrayIcon:
    def __init__(self) -> None:
        self._tray = QSystemTrayIcon(_load_tray_icon())
        self._tray.setToolTip(app_display_name)
        self._menu = QMenu()

        show_action = QAction(show_launcher_label, self._menu)
        show_action.triggered.connect(lambda: events.emit("app:show_launcher"))
        prefs_action = QAction("Preferences", self._menu)
        prefs_action.triggered.connect(lambda: events.emit("app:show_preferences"))
        about_action = QAction("About", self._menu)
        about_action.triggered.connect(lambda: events.emit("app:show_preferences", "about"))
        quit_action = QAction("Exit", self._menu)
        quit_action.triggered.connect(lambda: events.emit("app:quit"))

        self._menu.addAction(show_action)
        self._menu.addAction(prefs_action)
        self._menu.addAction(about_action)
        self._menu.addSeparator()
        self._menu.addAction(quit_action)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            events.emit("app:show_launcher")

    def switch(self, enable: bool) -> None:
        self._tray.setVisible(enable)
