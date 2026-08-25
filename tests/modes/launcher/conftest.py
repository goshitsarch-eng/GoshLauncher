from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_launcher_lookups() -> None:
    from ulauncher.modes.launcher.app_usage import reset_gnome_app_usage_cache
    from ulauncher.modes.launcher.bookmarks import invalidate_bookmarks
    from ulauncher.modes.launcher.commands import invalidate_command_lookup
    from ulauncher.modes.launcher.paths import invalidate_path_lookup
    from ulauncher.modes.launcher.recents import invalidate_recent_files

    invalidate_path_lookup()
    invalidate_command_lookup()
    invalidate_bookmarks()
    invalidate_recent_files()
    reset_gnome_app_usage_cache()
    yield
    invalidate_path_lookup()
    invalidate_command_lookup()
    invalidate_bookmarks()
    invalidate_recent_files()
    reset_gnome_app_usage_cache()


@pytest.fixture(autouse=True)
def _no_host_live_watches(monkeypatch: pytest.MonkeyPatch) -> None:
    # LiveSearchWatcher.start would otherwise open an X Display / Wayland
    # socket during unit tests when python-xlib and xvfb are present.
    class _NoHostWatch:
        def start(self, _on_change: object, **_kwargs: object) -> bool:
            return False

        def stop(self) -> None:
            return None

    monkeypatch.setattr("ulauncher.modes.launcher.x11_live.X11LiveWatch", _NoHostWatch)
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_workspaces.ExtWorkspaceLiveWatch", _NoHostWatch)
    monkeypatch.setattr("ulauncher.modes.launcher.wayland_toplevels.ExtForeignLiveWatch", _NoHostWatch)
    monkeypatch.setattr("ulauncher.modes.launcher.atspi_windows.AtspiLiveWatch", _NoHostWatch)
    monkeypatch.setattr("ulauncher.modes.launcher.atspi_windows.list_atspi_windows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("ulauncher.modes.launcher.atspi_windows.grab_atspi_focus", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("ulauncher.modes.launcher.atspi_windows.atspi_focus_ranks", lambda *_args, **_kwargs: {})
