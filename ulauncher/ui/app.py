"""The Qt application: lifecycle, single instance, EventBus surface, windows."""

from __future__ import annotations

import logging
import os
import signal
import time
from typing import TYPE_CHECKING, Any

import ulauncher
from ulauncher import app_display_name, first_run, paths
from ulauncher.core import UlauncherCore
from ulauncher.utils import scheduling
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings

if TYPE_CHECKING:
    from ulauncher.internals.result import Result
    from ulauncher.internals.results_update import ResultsUpdate
    from ulauncher.ui.launcher_window import LauncherWindow

logger = logging.getLogger(__name__)
events = EventBus("app")


class UlauncherApp:
    query = ""
    core: UlauncherCore
    _persistent: bool = False
    _tray_icon: Any = None
    _launcher_window: LauncherWindow | None = None
    _preferences_window: Any = None
    _dbus_service: Any = None
    _quit_timer: scheduling.Context | None = None

    def __init__(self) -> None:
        from PySide6.QtGui import QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
        from PySide6.QtWidgets import QApplication

        # qqc2-desktop-style makes QML controls render like native KDE widgets;
        # respect an explicit user override via the standard env var.
        if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
            QQuickStyle.setStyle("org.kde.desktop")

        self.qt_app = QApplication([])
        self.qt_app.setApplicationName("ulauncher")
        self.qt_app.setApplicationDisplayName(app_display_name)
        self.qt_app.setDesktopFileName(ulauncher.app_id)
        self.qt_app.setQuitOnLastWindowClosed(False)
        icon = QIcon.fromTheme("ulauncher")
        if icon.isNull():
            icon = QIcon(os.path.join(paths.ASSETS, "icons", "system", "apps", "ulauncher.svg"))
        self.qt_app.setWindowIcon(icon)

        from ulauncher.ui.icons import AppIconProvider

        self.qml_engine = QQmlApplicationEngine()
        self.qml_engine.addImageProvider(AppIconProvider.NAME, AppIconProvider())

        self._toggle_last_time_us = 0
        events.set_self(self)

    # Lifecycle

    def start(self, *, activate: bool = True) -> int:
        from ulauncher.ui import dbus_service

        service = dbus_service.register(self)
        if service is None:
            # Another instance owns the bus name; delegate and exit.
            logger.info("%s is already running", app_display_name)
            if activate:
                dbus_service.call_running_instance("ShowWindow")
            return 0
        self._dbus_service = service
        self._setup()
        if activate:
            self.show_launcher()
        return self.qt_app.exec()

    def _setup(self) -> None:
        settings = Settings.load()
        self.core = UlauncherCore()

        from ulauncher.ui.theme import apply_color_scheme

        apply_color_scheme(getattr(settings, "color_scheme", "system"))

        self._persistent = settings.is_persistent()
        if self._persistent:
            # Warm the modes so extension handlers register and enabled extensions start.
            def _warm_triggers() -> None:
                if self._launcher_window is None:
                    self.core.load_triggers()

            scheduling.run_when_idle(_warm_triggers)

        if settings.show_tray_icon and self._persistent:
            self.toggle_tray_icon(True)

        # SIGTERM must interrupt the Qt loop; the interval keeps the interpreter
        # waking up so Python-level signal handlers actually run.
        signal.signal(signal.SIGTERM, lambda *_: self.quit())
        signal.signal(signal.SIGINT, lambda *_: self.quit())
        scheduling.interval(0.5, lambda: None)

        from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK
        from ulauncher.ui.hotkey_controller import HotkeyController

        hotkey = settings.hotkey_show_app or DEFAULT_FALLBACK
        # Portal sessions die with the process, so this must run on every startup.
        portal_bound = HotkeyController.bind_session_hotkey(hotkey, self.toggle_window)

        if first_run:
            if HotkeyController.is_supported():
                if HotkeyController.setup_default(hotkey):
                    from ulauncher.modes.launcher.shortcut import format_accelerator

                    body = (
                        f"{app_display_name} has added a global keyboard shortcut: "
                        f'"{format_accelerator(hotkey)}" to your desktop settings'
                    )
                    self.show_notification("de_hotkey_auto_created", "Global shortcut created", body)
            elif not portal_bound:
                body = (
                    f"{app_display_name} doesn't support setting global keyboard shortcuts for your desktop. "
                    "There are more details on this in the preferences view."
                )
                self.show_notification("de_hotkey_unsupported", "Cannot create global shortcut", body)

    # Core interaction

    def query_changed(self, query_str: str) -> None:
        """Run the new query string through the core and render the results."""
        self.query = query_str.lstrip()
        self.core.set_query(self.query, self.show_results)

    def activate_result(self, result: Result, alt: bool) -> None:
        self.core.activate_result(result, self.show_results, alt)

    def handle_backspace(self, query_str: str) -> bool:
        """Whether a mode consumed the backspace by rewriting the query (smart backspace)."""
        return self.core.handle_backspace(query_str)

    def window_ready(self) -> None:
        self.core.load_triggers(force=True)
        self.core.set_query(self.query, self.show_results)

    def show_results(self, update: ResultsUpdate) -> None:
        """Render results in the launcher window if it is currently open."""
        if self._launcher_window is not None and self._launcher_window.visible:
            self._launcher_window.show_results(update)

    # EventBus surface (also reachable over D-Bus TriggerEvent)

    @events.on
    def set_query(self, value: str, update_input: bool = True) -> None:
        self.query = value.lstrip()
        if update_input and self._launcher_window is not None:
            self._launcher_window.set_input(self.query)

    @events.on
    def reload_query(self) -> None:
        if self._launcher_window is not None and self._launcher_window.visible:
            self.core.set_query(self.query, self.show_results)

    @events.on
    def prefs_saved(self, keys: tuple[str, ...]) -> None:
        from ulauncher.modes.launcher.prefs_live import live_pref_actions

        if "color_scheme" in keys:
            from ulauncher.ui.theme import apply_color_scheme

            apply_color_scheme(getattr(Settings.load(), "color_scheme", "system"))
        actions = live_pref_actions(keys)
        if actions and self._launcher_window is not None:
            self._launcher_window.apply_live_prefs(actions)

    @events.on
    def rebind_hotkey(self, accel: str) -> None:
        from ulauncher.ui.hotkey_controller import HotkeyController

        HotkeyController.rebind_portal(accel)

    @events.on
    def show_notification(self, notification_id: str | None, title: str, body: str, default_action: str = "-") -> None:
        from ulauncher.ui.notify import show_notification

        show_notification(title, body)

    @events.on
    def clipboard_store(self, data: str) -> None:
        from ulauncher.ui.clipboard import clipboard_set_text

        clipboard_set_text(data)

    @events.on
    def copy_and_close(self, data: str) -> None:
        self.clipboard_store(data)
        self.close_launcher()

    @events.on
    def show_launcher(self) -> None:
        from ulauncher.modes.launcher.popup_gate import can_open_popup, popup_open_entry_text, should_close_on_session
        from ulauncher.modes.launcher.session_state import session_popup_blockers

        locked, greeter, limits = session_popup_blockers()
        if should_close_on_session(locked, greeter, limits):
            self.close_launcher()
            return
        if not can_open_popup(False, False, locked, greeter, limits):
            return

        self._cancel_quit_timer()
        self.query = popup_open_entry_text()

        if self._launcher_window is None:
            from ulauncher.ui.launcher_window import LauncherWindow

            self._launcher_window = LauncherWindow(self)
        self._launcher_window.set_input(self.query)
        self._launcher_window.show()
        scheduling.run_when_idle(self.window_ready)

    @events.on
    def close_launcher(self) -> None:
        self.request_close()

    def request_close(self, save_query: bool = False) -> None:
        if self._launcher_window is not None and self._launcher_window.visible:
            self._launcher_window.hide()
            from ulauncher.core import reject_async_paints

            # Drop in-flight async provider paints so a stale finish can't repaint later
            reject_async_paints()
        self.query = ""
        self._maybe_quit_later()

    def _maybe_quit_later(self) -> None:
        if self._persistent or self._windows_open():
            return
        # Clipboard managers need time to snapshot our clipboard ownership after a
        # copy action; there is no "snapshot done" event, so delay the quit by 1s.
        self._cancel_quit_timer()

        def _quit_if_still_idle() -> None:
            if not self._windows_open() and not self._persistent:
                self.quit()

        self._quit_timer = scheduling.timer(1, _quit_if_still_idle)

    def _cancel_quit_timer(self) -> None:
        if self._quit_timer is not None:
            self._quit_timer.cancel()
            self._quit_timer = None

    def _windows_open(self) -> bool:
        launcher_open = self._launcher_window is not None and self._launcher_window.visible
        prefs_open = self._preferences_window is not None and self._preferences_window.visible
        return launcher_open or prefs_open

    @events.on
    def show_preferences(self, page: str | None = None) -> None:
        if not self._persistent and not self._windows_open():
            logger.error("You have to start %s before you can open preferences.", app_display_name)
            self.quit()
            return

        self._cancel_quit_timer()
        if self._launcher_window is not None:
            self._launcher_window.hide()

        if self._preferences_window is None:
            from ulauncher.ui.preferences.prefs_window import PreferencesWindow

            self._preferences_window = PreferencesWindow(self)
        self._preferences_window.show(page)

    def preferences_closed(self) -> None:
        self._maybe_quit_later()

    def activate_query(self, query_str: str) -> None:
        self.show_launcher()
        self.set_query(query_str)

    def toggle_window(self) -> None:
        """Toggle window visibility - for explicit toggle requests only."""
        from ulauncher.modes.launcher.shortcut import should_ignore_shortcut_repeat

        now_us = time.monotonic_ns() // 1000
        if should_ignore_shortcut_repeat(now_us, self._toggle_last_time_us):
            self._toggle_last_time_us = now_us
            return
        self._toggle_last_time_us = now_us

        if self._launcher_window is not None and self._launcher_window.visible:
            self.request_close()
        else:
            self.show_launcher()

    @events.on
    def toggle_tray_icon(self, enable: bool) -> None:
        if not self._tray_icon:
            from ulauncher.ui.tray_icon import TrayIcon

            self._tray_icon = TrayIcon()
        # A tray icon is only meaningful while the app keeps running in the background.
        self._tray_icon.switch(enable and self._persistent)

    @events.on
    def toggle_hold(self, value: bool) -> None:
        if value != self._persistent:
            self._persistent = value
            self.toggle_tray_icon(Settings.load().show_tray_icon)
            self._maybe_quit_later()

    def _cleanup(self) -> None:
        from contextlib import suppress
        from shutil import rmtree

        from ulauncher.modes.extensions.extension_service import ext_service

        ext_service.detach_preview_log()

        # Prune staging entries, except recent entries (within 1h) since they could be ongoing installs via the cli
        threshold = time.time() - 3600
        with suppress(OSError):
            for e in os.scandir(paths.EXTENSIONS_STAGING):
                with suppress(OSError):
                    if e.stat(follow_symlinks=False).st_mtime > threshold:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        rmtree(e.path, ignore_errors=True)
                    else:
                        os.unlink(e.path)

    @events.on
    def quit(self) -> None:
        self._cleanup()
        self.qt_app.quit()
