from __future__ import annotations

from ulauncher.modes.launcher.async_paint import should_run_async_paint, should_schedule_async_paint


def test_async_paint_gates_match_goshos() -> None:
    assert should_schedule_async_paint(False, True) is True
    assert should_schedule_async_paint(True, True) is False
    assert should_schedule_async_paint(False, False) is False
    assert should_run_async_paint(True, True) is True
    assert should_run_async_paint(False, True) is False
    assert should_run_async_paint(True, False) is False
