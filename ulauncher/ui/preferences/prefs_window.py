"""Preferences window: a Kirigami settings app driven by one backend QObject."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

import ulauncher
from ulauncher.utils.settings import Settings

if TYPE_CHECKING:
    from ulauncher.ui.app import UlauncherApp

logger = logging.getLogger(__name__)

QML_DIR = os.path.join(os.path.dirname(__file__), "..", "qml")

PAGE_ALIASES = {
    "preferences": "general",
    "pref": "general",
    "appearance": "general",
    "launcher": "general",
    "chrome": "general",
    "web": "web-search",
    "websearch": "web-search",
    "web_search": "web-search",
    "keyboard": "general",
    "hotkey": "general",
    "shortcut": "general",
    "help": "about",
    "session": "desktop",
}
PAGES = ("general", "features", "web-search", "shortcuts", "extensions", "desktop", "about")


class PrefsBackend(QObject):
    shortcutsChanged = Signal()
    extensionsChanged = Signal()
    settingChanged = Signal(str)
    extOpFinished = Signal(bool, str)
    updateCheckFinished = Signal(str, bool, str)  # ext_id, update_available, message or commit hash
    hotkeyChanged = Signal()

    def __init__(self, app: UlauncherApp) -> None:
        super().__init__()
        self._app = app

    # Generic settings access

    @Slot(str, result="QVariant")
    def getSetting(self, key: str) -> Any:
        return Settings.load().get(key.replace("-", "_"))

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        key = key.replace("-", "_")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        Settings.load().save({key: value})
        self.settingChanged.emit(key)

    @Slot(str, result="QVariant")
    def lookOptions(self, _dummy: str = "") -> Any:
        from ulauncher.modes.launcher.looks import LOOKS

        return [{"id": look["id"], "title": look["title"], "description": look["description"]} for look in LOOKS]

    @Slot(str)
    def applyLook(self, look_id: str) -> None:
        from ulauncher.modes.launcher.looks import apply_look_chrome

        apply_look_chrome(Settings.load(), look_id)

    @Slot(result="QVariant")
    def webSearchEngines(self) -> Any:
        from ulauncher.modes.launcher.web import SEARCH_ENGINES

        return [{"id": engine["id"], "title": engine["label"]} for engine in SEARCH_ENGINES]

    # About info

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return ulauncher.version

    @Property(str, constant=True)
    def appName(self) -> str:
        return ulauncher.app_display_name

    # Global hotkey

    @Property(str, notify=hotkeyChanged)
    def currentShortcutLabel(self) -> str:
        from ulauncher.modes.launcher.shortcut import format_accelerator
        from ulauncher.ui.hotkey_controller import HotkeyController

        return format_accelerator(HotkeyController.current_accelerator())

    @Property(bool, constant=True)
    def hotkeySupported(self) -> bool:
        from ulauncher.ui.hotkey_controller import HotkeyController

        return HotkeyController.is_supported() or self.hotkeyUsesPortal

    @Property(bool, constant=True)
    def hotkeyUsesPortal(self) -> bool:
        from ulauncher.modes.launcher.global_shortcuts import should_bind_portal
        from ulauncher.utils.environment import DESKTOP_ID

        return should_bind_portal(DESKTOP_ID)

    @Property(bool, constant=True)
    def isPlasma(self) -> bool:
        from ulauncher.ui.hotkey_controller import HotkeyController

        return HotkeyController.is_plasma()

    @Slot()
    def openPlasmaShortcuts(self) -> None:
        from ulauncher.ui.hotkey_controller import HotkeyController

        HotkeyController.show_dialog()

    @Slot(int, int, result=str)
    def acceleratorFromKey(self, key: int, modifiers: int) -> str:
        """Convert a QML key event to the stored accelerator format ("<Control>space").
        Returns "" for modifier-only or unacceptable captures."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence

        from ulauncher.modes.launcher.shortcut import accelerator_needs_modifier

        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R):
            return ""
        key_name = QKeySequence(key).toString().lower()
        if not key_name:
            return ""
        mods = ""
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            mods += "<Super>"
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mods += "<Control>"
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mods += "<Shift>"
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mods += "<Alt>"
        if not mods and accelerator_needs_modifier(key_name):
            return ""
        return f"{mods}{key_name}"

    @Slot(str, result=bool)
    def applyAccelerator(self, accel: str) -> bool:
        from ulauncher.ui.hotkey_controller import HotkeyController

        applied = HotkeyController.apply_accelerator(accel)
        self.hotkeyChanged.emit()
        return applied

    @Slot(str, result=str)
    def formatAccelerator(self, accel: str) -> str:
        from ulauncher.modes.launcher.shortcut import format_accelerator

        return format_accelerator(accel)

    # Session / autostart

    @Property(bool, constant=True)
    def autostartManaged(self) -> bool:
        from ulauncher.utils.systemd_controller import SystemdController

        return SystemdController("ulauncher").status().can_start

    @Slot(result=bool)
    def autostartEnabled(self) -> bool:
        from ulauncher.utils.systemd_controller import SystemdController

        status = SystemdController("ulauncher").status()
        if status.can_start:
            return status.is_enabled
        return bool(Settings.load().keep_alive)

    @Slot(bool, result=bool)
    def setAutostart(self, enabled: bool) -> bool:
        from ulauncher.utils.eventbus import EventBus
        from ulauncher.utils.systemd_controller import SystemdController

        controller = SystemdController("ulauncher")
        if controller.status().can_start:
            try:
                controller.toggle(enabled)
            except OSError:
                logger.exception("Could not toggle autostart")
                return False
        else:
            Settings.load().save({"keep_alive": enabled})
        EventBus().emit("app:toggle_hold", enabled)
        return True

    @Property(bool, constant=True)
    def isX11(self) -> bool:
        from ulauncher.utils.environment import IS_X11

        return IS_X11

    # Keyword shortcuts editor

    @Slot(result="QVariant")
    def shortcuts(self) -> Any:
        from ulauncher.modes.shortcuts.shortcuts import Shortcuts

        items = []
        for shortcut_id, shortcut in Shortcuts.load().items():
            items.append(
                {
                    "id": shortcut_id,
                    "name": shortcut.name,
                    "keyword": shortcut.keyword,
                    "cmd": shortcut.cmd,
                    "icon": shortcut.icon or "insert-link",
                    "run_without_argument": shortcut.run_without_argument,
                    "is_default_search": shortcut.is_default_search,
                }
            )
        items.sort(key=lambda item: str(item["name"]).lower())
        return items

    @Slot("QVariant", result=bool)
    def saveShortcut(self, data: Any) -> bool:
        from ulauncher.modes.shortcuts.shortcuts import Shortcut, Shortcuts

        fields = dict(data.toVariant()) if hasattr(data, "toVariant") else dict(data)
        if not (fields.get("name") and fields.get("keyword") and fields.get("cmd")):
            return False
        shortcuts = Shortcuts.load()
        shortcut_id = fields.get("id") or str(uuid4())
        existing = shortcuts.get(shortcut_id)
        shortcut = Shortcut(
            id=shortcut_id,
            name=str(fields["name"]),
            keyword=str(fields["keyword"]),
            cmd=str(fields["cmd"]),
            icon=str(fields.get("icon") or ""),
            run_without_argument=bool(fields.get("run_without_argument")),
            is_default_search=bool(fields.get("is_default_search")),
            added=existing.added if existing else int(time.time()),
        )
        shortcuts.save({shortcut_id: shortcut})
        self.shortcutsChanged.emit()
        return True

    @Slot(str)
    def removeShortcut(self, shortcut_id: str) -> None:
        from ulauncher.modes.shortcuts.shortcuts import Shortcuts

        Shortcuts.load().save({shortcut_id: None})
        self.shortcutsChanged.emit()

    # Extensions

    def _ext_service(self) -> Any:
        from ulauncher.modes.extensions.extension_service import ext_service

        return ext_service

    def _ext_status(self, record: Any) -> str:
        from ulauncher.modes.extensions.extension_record import PreviewExtensionRecord

        if isinstance(record, PreviewExtensionRecord):
            return "preview"
        if record.has_error():
            return "error"
        if not record.is_enabled:
            return "off"
        return "on" if self._ext_service().is_running(record) else "stopped"

    @Slot(result="QVariant")
    def extensions(self) -> Any:
        service = self._ext_service()
        items = []
        for record in service.iterate(sort=True):
            error = record.get_error()
            manifest = record.display_manifest
            triggers = [
                {
                    "id": trigger_id,
                    "name": trigger.name,
                    "description": trigger.description,
                    "keyword": trigger.keyword or trigger.default_keyword,
                    "has_keyword": bool(trigger.keyword or trigger.default_keyword),
                }
                for trigger_id, trigger in record.triggers.items()
            ]
            prefs = []
            for pref_id, pref in record.preferences.items():
                options = pref.options or []
                normalized_options = []
                for option in options:
                    if isinstance(option, dict):
                        normalized_options.append(
                            {
                                "value": str(option.get("value", "")),
                                "text": str(option.get("text", option.get("value", ""))),
                            }
                        )
                    else:
                        normalized_options.append({"value": str(option), "text": str(option)})
                prefs.append(
                    {
                        "id": pref_id,
                        "name": pref.name,
                        "type": pref.type,
                        "description": pref.description,
                        "value": pref.value if pref.value is not None else pref.default_value,
                        "options": normalized_options,
                        "min": pref.min if pref.min is not None else 0,
                        "max": pref.max if pref.max is not None else 100,
                    }
                )
            items.append(
                {
                    "id": record.id,
                    "name": manifest.name or record.id,
                    "authors": manifest.authors,
                    "icon": record.get_icon_value() or "application-x-addon",
                    "status": self._ext_status(record),
                    "enabled": record.is_enabled,
                    "manageable": record.is_manageable(),
                    "url": record.website_url or record.state.url,
                    "updated": record.state.commit_time[:10] if record.state.commit_time else "",
                    "instructions": manifest.instructions or "",
                    "error": (error.message or error.type) if error else "",
                    "triggers": triggers,
                    "prefs": prefs,
                    "has_update_url": bool(record.update_url),
                }
            )
        return items

    @Slot(str)
    def addExtension(self, url: str) -> None:
        service = self._ext_service()

        def on_success(_record: Any) -> None:
            self.extensionsChanged.emit()
            self.extOpFinished.emit(True, "Extension installed")

        def on_error(error: Exception) -> None:
            logger.warning("Extension install failed: %s", error)
            self.extOpFinished.emit(False, str(error))

        service.install(url.strip(), on_success, on_error)

    @Slot(str)
    def removeExtension(self, ext_id: str) -> None:
        service = self._ext_service()
        record = service.get(ext_id)
        if record is None:
            return

        def on_done() -> None:
            self.extensionsChanged.emit()
            self.extOpFinished.emit(True, "Extension removed")

        def on_error(error: Exception) -> None:
            self.extOpFinished.emit(False, str(error))

        service.uninstall(record, on_done, on_error)

    @Slot(str, bool)
    def toggleExtension(self, ext_id: str, enabled: bool) -> None:
        service = self._ext_service()
        record = service.get(ext_id)
        if record is not None:
            service.toggle_enabled(record, enabled)
            self.extensionsChanged.emit()

    @Slot(str)
    def updateExtension(self, ext_id: str) -> None:
        service = self._ext_service()
        record = service.get(ext_id)
        if record is None:
            return

        def on_success(updated: bool) -> None:
            self.extensionsChanged.emit()
            self.updateCheckFinished.emit(ext_id, updated, "Updated" if updated else "Already up to date")

        def on_error(error: Exception) -> None:
            self.updateCheckFinished.emit(ext_id, False, str(error))

        service.update(record, on_success, on_error)

    @Slot(str, "QVariant")
    def saveExtensionPrefs(self, ext_id: str, data: Any) -> None:
        service = self._ext_service()
        record = service.get(ext_id)
        if record is None:
            return
        payload = dict(data.toVariant()) if hasattr(data, "toVariant") else dict(data)
        service.save_user_preferences(record, payload)
        self.extensionsChanged.emit()

    @Slot(str)
    def openUrl(self, url: str) -> None:
        from ulauncher.utils.launch_detached import open_detached

        open_detached(url)


class PreferencesWindow:
    def __init__(self, app: UlauncherApp) -> None:
        from PySide6.QtQml import QQmlComponent

        self._app = app
        self.backend = PrefsBackend(app)
        engine = app.qml_engine
        qml_path = os.path.normpath(os.path.join(QML_DIR, "PreferencesWindow.qml"))
        component = QQmlComponent(engine, QUrl.fromLocalFile(qml_path))
        if component.isError():
            for error in component.errors():
                logger.error("QML error: %s", error.toString())
            msg = "Could not load PreferencesWindow.qml"
            raise RuntimeError(msg)
        self._window = component.createWithInitialProperties({"backend": self.backend}, engine.rootContext())
        if self._window is None:
            msg = "Could not instantiate PreferencesWindow.qml"
            raise RuntimeError(msg)
        self._window.visibleChanged.connect(self._on_visible_changed)

    def _on_visible_changed(self) -> None:
        if not self.visible:
            self._app.preferences_closed()

    @property
    def visible(self) -> bool:
        return bool(self._window.property("visible"))

    def show(self, page: str | None = None) -> None:
        page = PAGE_ALIASES.get(page or "", page or "")
        if page in PAGES:
            self._window.setProperty("requestedPage", page)
        self._window.setProperty("visible", True)
        raise_ = getattr(self._window, "raise_", None)
        if callable(raise_):
            raise_()
        self._window.requestActivate()
