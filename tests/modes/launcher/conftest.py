from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_launcher_lookups() -> None:
    from ulauncher.modes.launcher.commands import invalidate_command_lookup
    from ulauncher.modes.launcher.paths import invalidate_path_lookup

    invalidate_path_lookup()
    invalidate_command_lookup()
    yield
    invalidate_path_lookup()
    invalidate_command_lookup()
