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
