from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.gi import GioUnix
from ulauncher.modes.apps.app_mode import AppMode
from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
from ulauncher.utils.settings import Settings

ENTRIES_DIR = Path(__file__).parent.joinpath("mock_desktop_entries").resolve()


class _GAppInfoOnly:
    """GNOME 50 can type some installed apps as GAppInfo without desktop methods."""

    def get_display_name(self) -> str:
        return "Notes"

    def get_string(self, _name: str) -> str:
        return ""

    def get_description(self) -> str:
        return "Write notes"

    def get_id(self) -> str:
        return "notes.desktop"

    def get_executable(self) -> str:
        return "notes"

    def get_boolean(self, _name: str) -> bool:
        return False


class _ThrowsActions(_GAppInfoOnly):
    def list_actions(self) -> list[str]:
        message = "invalid desktop encoding"
        raise RuntimeError(message)


class _BadEncodingApp:
    def get_executable(self) -> str:
        message = "invalid desktop encoding"
        raise RuntimeError(message)


def test_app_result_skips_missing_desktop_only_methods() -> None:
    app = AppResult(_GAppInfoOnly())  # type: ignore[arg-type]
    assert app.name == "Notes"
    assert app.generic_name == ""
    assert app.keywords == []
    assert list(app.actions) == ["launch"]


def test_app_result_keeps_row_when_list_actions_throws() -> None:
    app = AppResult(_ThrowsActions())  # type: ignore[arg-type]
    assert app.name == "Notes"
    assert ACTION_PREFIX not in "".join(app.actions)


def test_get_triggers_skips_one_bad_desktop_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    good = GioUnix.DesktopAppInfo.new_from_filename(str(ENTRIES_DIR / "trueapp.desktop"))
    assert good is not None
    settings = Settings()
    settings.enable_application_mode = True
    settings.disable_desktop_filters = True
    monkeypatch.setattr(Settings, "load", classmethod(lambda _cls, **_kwargs: settings))
    monkeypatch.setattr(
        GioUnix.DesktopAppInfo,
        "get_all",
        staticmethod(lambda: [_BadEncodingApp(), good]),
    )
    names = [app.name for app in AppMode().get_triggers()]
    assert names == ["TrueApp - Full Name"]


def test_installed_apps_is_read_once_and_invalidated_on_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.modes.apps import app_mode as app_mode_mod

    # Rebuilding this scans the desktop-entry directories, and both the launcher's per-keystroke
    # app search and the core's per-open trigger load ask for it.
    calls: list[int] = []

    class _Entry:
        def get_executable(self) -> str:
            return "/bin/true"

        def get_display_name(self) -> str:
            return "Gosh Probe"

        def get_show_in(self) -> bool:
            return True

        def get_nodisplay(self) -> bool:
            return False

        def get_id(self) -> str:
            return "gosh-probe.desktop"

    def get_all() -> list[_Entry]:
        calls.append(1)
        return [_Entry()]

    monkeypatch.setattr(app_mode_mod.GioUnix.DesktopAppInfo, "get_all", staticmethod(get_all))
    monkeypatch.setattr(app_mode_mod, "_installed_app_result", lambda app, _settings: app)
    app_mode_mod.invalidate_installed_apps()
    try:
        assert app_mode_mod.installed_apps()
        assert app_mode_mod.installed_apps()
        assert list(AppMode().get_triggers())
        assert len(calls) == 1

        app_mode_mod.invalidate_installed_apps()
        assert app_mode_mod.installed_apps()
        assert len(calls) == 2
    finally:
        app_mode_mod.invalidate_installed_apps()
