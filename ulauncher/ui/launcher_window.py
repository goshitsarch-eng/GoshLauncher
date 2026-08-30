"""The launcher popup: a frameless Kirigami-styled QML window plus its backend object.

The backend is the QML-facing surface: it owns the results model and selection,
relays key navigation (policy lives in ulauncher.modes.launcher.*), and forwards
query edits to the app. The window is created once and shown/hidden per toggle.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from ulauncher.modes.launcher.looks import chrome_from_settings, get_look, icon_size_for_look
from ulauncher.modes.launcher.paint_selection import paint_selection_index, result_selection_key
from ulauncher.modes.launcher.selection_math import is_selectable_result, next_activatable_index
from ulauncher.ui.results_model import ResultsModel
from ulauncher.utils.settings import Settings

if TYPE_CHECKING:
    from ulauncher.internals.result import Result
    from ulauncher.internals.results_update import ResultsUpdate
    from ulauncher.ui.app import UlauncherApp

logger = logging.getLogger(__name__)

QML_DIR = os.path.join(os.path.dirname(__file__), "qml")


class LauncherBackend(QObject):
    selectedIndexChanged = Signal()
    chromeChanged = Signal()
    queryTextRequested = Signal(str)
    closeRequested = Signal()

    def __init__(self, app: UlauncherApp) -> None:
        super().__init__()
        self._app = app
        self._model = ResultsModel()
        self._selected = -1
        self._last_query_str = ""
        self._chrome: dict[str, object] = {}
        self._settings = Settings.load()
        self.reload_chrome()

    def reload_chrome(self) -> None:
        self._settings = Settings.load(force=True)
        self._chrome = dict(chrome_from_settings(self._settings))
        self.chromeChanged.emit()

    # Chrome properties for QML

    @Property(QObject, constant=True)
    def model(self) -> ResultsModel:  # type: ignore[override]
        return self._model

    @Property(int, notify=selectedIndexChanged)
    def selectedIndex(self) -> int:
        return self._selected

    @Property(int, notify=chromeChanged)
    def windowWidth(self) -> int:
        return max(400, min(1200, int(self._settings.base_width or 600)))

    @Property(int, notify=chromeChanged)
    def resultsMaxHeight(self) -> int:
        return max(160, min(800, int(self._settings.results_max_height or 400)))

    @Property(int, notify=chromeChanged)
    def iconSize(self) -> int:
        return icon_size_for_look(self._chrome, str(self._chrome.get("density", "comfortable")))

    @Property(bool, notify=chromeChanged)
    def compactDensity(self) -> bool:
        return self._chrome.get("density") == "compact"

    @Property(bool, notify=chromeChanged)
    def showSearchIcon(self) -> bool:
        return bool(self._chrome.get("show_search_icon", True))

    @Property(bool, notify=chromeChanged)
    def showResultIcons(self) -> bool:
        return bool(self._chrome.get("show_result_icons", True))

    @Property(bool, notify=chromeChanged)
    def showDescriptions(self) -> bool:
        return bool(self._chrome.get("show_descriptions", True))

    @Property(bool, notify=chromeChanged)
    def showNumbers(self) -> bool:
        return bool(self._chrome.get("show_numbers", False))

    @Property(bool, notify=chromeChanged)
    def positionTop(self) -> bool:
        return self._chrome.get("position") == "top"

    @Property(bool, notify=chromeChanged)
    def closeOnFocusOut(self) -> bool:
        return bool(self._settings.close_on_focus_out)

    @Property(str, notify=chromeChanged)
    def placeholderText(self) -> str:
        return str(get_look(self._settings.look_id).get("hint") or "Search...")

    # Results handling (called from Python)

    def show_results(self, update: ResultsUpdate) -> None:
        query_str = str(update["query"])
        previous_key = None
        if update["append"] or query_str == self._last_query_str:
            previous_key = result_selection_key(self._model.result_at(self._selected), max(self._selected, 0))
        self._model.set_results(update["results"], update["query"].argument or query_str, append=update["append"])
        self._last_query_str = query_str

        results = self._model.results
        if previous_key is not None:
            index = paint_selection_index(previous_key, results)
        else:
            index = self._preselect_index(results, update["selected_name"])
        self._set_selected(index)

    def _preselect_index(self, results: list[Result], selected_name: str | None) -> int:
        if selected_name:
            for i, result in enumerate(results):
                if result.name == selected_name and is_selectable_result(result):
                    return i
        return paint_selection_index(None, results)

    def _set_selected(self, index: int) -> None:
        if index != self._selected:
            self._selected = index
            self.selectedIndexChanged.emit()

    # Slots called from QML

    @Slot(str)
    def textEdited(self, text: str) -> None:
        self._app.query_changed(text)

    @Slot(int)
    def navigate(self, delta: int) -> None:
        results = self._model.results
        if not results:
            return
        current = max(self._selected, 0)
        self._set_selected(next_activatable_index(current, delta, results))

    @Slot(int)
    def setHoverSelection(self, index: int) -> None:
        result = self._model.result_at(index)
        if result is not None and is_selectable_result(result):
            self._set_selected(index)

    @Slot(bool)
    def activateSelected(self, alt: bool) -> None:
        result = self._model.result_at(self._selected)
        if result is None:
            return
        self._activate(result, alt)

    @Slot(int, bool)
    def activateIndex(self, index: int, alt: bool) -> None:
        result = self._model.result_at(index)
        if result is None or not is_selectable_result(result):
            return
        self._set_selected(index)
        self._activate(result, alt)

    @Slot(int)
    def activateNumber(self, digit: int) -> None:
        """Alt+1..9: activate the digit'th highlightable row (headers excluded)."""
        if not self.showNumbers:
            return
        hinted = [i for i, r in enumerate(self._model.results) if r.highlightable]
        if 1 <= digit <= len(hinted):
            self.activateIndex(hinted[digit - 1], False)

    def _activate(self, result: Result, alt: bool) -> None:
        if not alt:
            # Hide before the action runs so slow launches don't leave the popup lingering
            self._app.request_close()
        self._app.activate_result(result, alt)

    @Slot(str, result=bool)
    def handleBackspace(self, text: str) -> bool:
        """Smart backspace: whether a mode consumed it by rewriting the query."""
        return self._app.handle_backspace(text)

    @Slot()
    def requestClose(self) -> None:
        self._app.request_close()

    @Slot()
    def showPreferences(self) -> None:
        self._app.show_preferences()


class LauncherWindow:
    """Owns the QML window instance; shown and hidden rather than recreated."""

    def __init__(self, app: UlauncherApp) -> None:
        from PySide6.QtQml import QQmlComponent

        self._app = app
        self.backend = LauncherBackend(app)
        engine = app.qml_engine
        self._component = QQmlComponent(engine, QUrl.fromLocalFile(os.path.join(QML_DIR, "LauncherWindow.qml")))
        if self._component.isError():
            for error in self._component.errors():
                logger.error("QML error: %s", error.toString())
            msg = "Could not load LauncherWindow.qml"
            raise RuntimeError(msg)
        context = engine.rootContext()
        self._window = self._component.createWithInitialProperties({"backend": self.backend}, context)
        if self._window is None:
            msg = "Could not instantiate LauncherWindow.qml"
            raise RuntimeError(msg)

    @property
    def visible(self) -> bool:
        return bool(self._window.property("visible"))

    def set_input(self, text: str) -> None:
        self.backend.queryTextRequested.emit(text)

    def show_results(self, update: ResultsUpdate) -> None:
        self.backend.show_results(update)

    def show(self) -> None:
        self.backend.reload_chrome()
        self._position()
        self._window.setProperty("visible", True)
        raise_ = getattr(self._window, "raise_", None)
        if callable(raise_):
            raise_()
        # pyrefly: ignore [missing-attribute]
        self._window.requestActivate()

    def hide(self) -> None:
        self._window.setProperty("visible", False)

    def apply_live_prefs(self, actions: set[str]) -> None:
        self.backend.reload_chrome()
        if "position" in actions or "layout" in actions:
            self._position()
        if "repaint" in actions and self.visible:
            self._app.query_changed(self._app.query)

    def _position(self) -> None:
        """Center on the primary screen's work area (X11; Wayland compositors place
        dialogs themselves and ignore programmatic positions)."""
        # pyrefly: ignore [missing-attribute]
        screen = self._window.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        # pyrefly: ignore [bad-specialization]
        width = min(self.backend.windowWidth, avail.width())
        x = avail.x() + (avail.width() - width) // 2
        y_factor = 0.12 if self.backend.positionTop else 0.22
        y = avail.y() + int(avail.height() * y_factor)
        self._window.setProperty("x", x)
        self._window.setProperty("y", y)
