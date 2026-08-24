from __future__ import annotations

from ulauncher.modes.launcher.unredirect import next_unredirect_action, unredirect_api


def test_unredirect_api_and_hold_release() -> None:
    assert unredirect_api(True, True) == "compositor"
    assert unredirect_api(False, True) == "display"
    assert unredirect_api(False, False) == ""
    assert next_unredirect_action(False, True, "compositor") == "hold"
    assert next_unredirect_action(True, True, "compositor") == "keep"
    assert next_unredirect_action(True, False, "compositor") == "release"
    assert next_unredirect_action(False, False, "compositor") == "keep"
    assert next_unredirect_action(False, True, "") == "keep"
