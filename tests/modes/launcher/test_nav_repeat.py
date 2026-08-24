from __future__ import annotations

from ulauncher.modes.launcher.nav_repeat import NAV_REPEAT_GAP_US, should_ignore_nav_repeat


def test_should_ignore_nav_repeat_matches_goshos() -> None:
    assert should_ignore_nav_repeat(65364, 0, 1000, 0) is False
    assert should_ignore_nav_repeat(65364, 65364, 2000, 0) is False
    assert should_ignore_nav_repeat(65364, 65364, 10000000 + 10000, 10000000) is True
    assert should_ignore_nav_repeat(65364, 65364, 10000000 + NAV_REPEAT_GAP_US, 10000000) is False
    assert should_ignore_nav_repeat(65362, 65364, 10000000 + 10000, 10000000) is False
