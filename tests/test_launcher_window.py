from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ulauncher.ui import launcher_window  # noqa: TID251


def test_launcher_window_retains_qml_component(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MagicMock()
    context = object()
    app.qml_engine.rootContext.return_value = context

    component = MagicMock()
    component.isError.return_value = False
    root_window = MagicMock()
    component.createWithInitialProperties.return_value = root_window
    component_factory = MagicMock(return_value=component)
    backend = MagicMock()

    monkeypatch.setattr("PySide6.QtQml.QQmlComponent", component_factory)
    monkeypatch.setattr(launcher_window, "LauncherBackend", lambda _app: backend)

    window = launcher_window.LauncherWindow(app)

    assert window._component is component
    assert window._window is root_window
    component.createWithInitialProperties.assert_called_once_with({"backend": backend}, context)
