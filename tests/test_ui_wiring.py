from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from pytest_mock import MockerFixture

from ulauncher.core import UlauncherCore
from ulauncher.internals import effects
from ulauncher.internals.query import Query
from ulauncher.internals.result import KeywordTrigger, Result
from ulauncher.internals.results_update import results_update
from ulauncher.modes.launcher.results import LauncherResult
from ulauncher.ui.app import UlauncherApp  # noqa: TID251
from ulauncher.ui.launcher_window import LauncherBackend, LauncherWindow  # noqa: TID251
from ulauncher.ui.preferences.prefs_window import PreferencesWindow, PrefsBackend  # noqa: TID251
from ulauncher.utils.settings import Settings


@pytest.fixture
def app(mocker: MockerFixture) -> UlauncherApp:
    instance = UlauncherApp.__new__(UlauncherApp)
    instance.core = UlauncherCore()
    instance._launcher_window = MagicMock(visible=True)
    mocker.patch("ulauncher.ui.app.events.self_arg", instance)
    mocker.patch.object(instance.core, "_remember_pick")
    return instance


def test_programmatic_query_runs_search(app: UlauncherApp, mocker: MockerFixture) -> None:
    search = mocker.patch.object(app.core, "set_query")
    app.set_query("  ~/Documents/")
    app._launcher_window.set_input.assert_called_once_with("~/Documents/")
    search.assert_called_once_with("~/Documents/", app.show_results)


@pytest.mark.parametrize(
    "effect", [effects.set_query("next "), effects.render_results([Result(name="Next")]), effects.do_nothing()]
)
def test_activation_keeps_popup_for_nonclosing_effects(
    app: UlauncherApp,
    mocker: MockerFixture,
    effect: effects.EffectMessage,
) -> None:
    mocker.patch.object(Settings, "load", return_value=Settings())
    close = mocker.patch.object(app, "request_close")
    mode = MagicMock()
    app.core._mode = mode
    mode.activate_result.side_effect = lambda _a, _r, _q, callback: callback(effect)
    backend = LauncherBackend(app)
    backend.show_results(results_update([LauncherResult(name="Open")], Query(None, "test"), None, False))
    backend.activateSelected(False)
    close.assert_not_called()
    if effect["type"] == effects.EffectType.RENDER_RESULTS:
        app._launcher_window.show_results.assert_called_once()


def test_activation_closes_for_terminal_effect(app: UlauncherApp, mocker: MockerFixture) -> None:
    mocker.patch.object(Settings, "load", return_value=Settings())
    close = mocker.patch.object(app, "request_close")
    mode = MagicMock()
    app.core._mode = mode
    mode.activate_result.side_effect = lambda _a, _r, _q, callback: callback(effects.close_window())
    backend = LauncherBackend(app)
    backend.show_results(results_update([LauncherResult(name="Open")], Query(None, "test"), None, False))
    backend.activateSelected(False)
    close.assert_called_once()


def test_keyword_activation_runs_new_query(app: UlauncherApp, mocker: MockerFixture) -> None:
    search = mocker.patch.object(app.core, "set_query")
    app.activate_result(KeywordTrigger(name="Extension", keyword="ext"), False)
    search.assert_called_once_with("ext ", app.show_results)


def test_tray_preference_is_applied(app: UlauncherApp, mocker: MockerFixture) -> None:
    mocker.patch.object(Settings, "load", return_value=Settings(show_tray_icon=False))
    toggle = mocker.patch.object(app, "toggle_tray_icon")
    app.prefs_saved(("show-tray-icon",))
    toggle.assert_called_once_with(False)


def test_preferences_open_in_nonpersistent_mode(app: UlauncherApp, mocker: MockerFixture) -> None:
    app._launcher_window = None
    app._persistent = False
    factory = mocker.patch("ulauncher.ui.preferences.prefs_window.PreferencesWindow")
    app.show_preferences("about")
    factory.return_value.show.assert_called_once_with("about")


@pytest.mark.parametrize(
    ("key", "modifiers", "expected"),
    [
        (Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier, "<Control>space"),
        (Qt.Key.Key_F6, Qt.KeyboardModifier.NoModifier, "F6"),
        (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, ""),
        (Qt.Key.Key_A, Qt.KeyboardModifier.AltModifier, "<Alt>a"),
        (Qt.Key.Key_PageDown, Qt.KeyboardModifier.MetaModifier, "<Super>Page_Down"),
        (Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier, ""),
    ],
)
def test_qt_shortcut_capture(key: Qt.Key, modifiers: Qt.KeyboardModifier, expected: str) -> None:
    backend = PrefsBackend(MagicMock())
    assert backend.acceleratorFromKey(key.value, modifiers.value) == expected


def test_shortcut_save_retains_id_and_icon(mocker: MockerFixture) -> None:
    from ulauncher.modes.shortcuts.shortcuts import Shortcuts

    shortcuts = Shortcuts()
    mocker.patch.object(Shortcuts, "load", return_value=shortcuts)
    mocker.patch.object(shortcuts, "save", side_effect=shortcuts.update)
    backend = PrefsBackend(MagicMock())
    shortcut_id = backend.saveShortcut(
        {"name": "Docs", "keyword": " docs ", "cmd": "https://example.com/%s", "icon": "/custom/icon.svg"}
    )
    assert shortcut_id
    assert shortcuts[shortcut_id].keyword == "docs"
    assert (
        backend.saveShortcut(
            {"id": shortcut_id, "name": "Docs updated", "keyword": "docs", "cmd": "https://example.com/search?q=%s"}
        )
        == shortcut_id
    )
    assert len(shortcuts) == 1
    assert shortcuts[shortcut_id].icon == "/custom/icon.svg"
    assert shortcuts[shortcut_id].name == "Docs updated"
    assert backend.saveShortcut({"name": "Invalid", "keyword": "two words", "cmd": "true"}) == ""


def test_preferences_retains_component(mocker: MockerFixture) -> None:
    component = mocker.patch("PySide6.QtQml.QQmlComponent").return_value
    component.isError.return_value = False
    prefs = PreferencesWindow(MagicMock())
    assert prefs._component is component


def test_monitor_selection_and_session_watcher(mocker: MockerFixture) -> None:
    from PySide6.QtCore import QRect

    mocker.patch.object(Settings, "load", return_value=Settings(render_on_screen="mouse-pointer-monitor"))
    component = mocker.patch("PySide6.QtQml.QQmlComponent").return_value
    component.isError.return_value = False
    component.createWithInitialProperties.return_value.property.return_value = 648
    primary = mocker.patch("ulauncher.ui.launcher_window.QGuiApplication.primaryScreen").return_value
    pointer = mocker.patch("ulauncher.ui.launcher_window.QGuiApplication.screenAt").return_value
    mocker.patch("ulauncher.ui.launcher_window.QCursor.pos")
    pointer.availableGeometry.return_value = QRect(1920, 0, 1280, 720)
    watcher = mocker.patch("ulauncher.modes.launcher.session_watch.SessionWatcher").return_value
    window = LauncherWindow(MagicMock())
    window.show()
    window._window.setProperty.assert_any_call("x", 2236)
    window._window.setProperty.assert_any_call("availableWidth", 1280)
    primary.availableGeometry.assert_not_called()
    watcher.start.assert_called_once()
    window.hide()
    watcher.stop.assert_called_once()
