"""Helpers to drive the MiniLoop (the non-Qt scheduling backend) in tests."""

from __future__ import annotations

from typing import Any, Callable

from ulauncher.utils.eventloop import get_loop


def process_pending_events(duration_sec: float = 0.05) -> None:
    """Run the event loop briefly so timers, idles, and fd watches dispatch."""
    loop = get_loop()
    loop.call_later(duration_sec, loop.quit)
    loop.run()


def drive_until(
    start: Callable[[Callable[[Any], None], Callable[[Exception], None]], None], timeout_sec: float = 10.0
) -> tuple[Any, Exception | None]:
    """Run a callback-based helper to completion under the loop; returns (result, error)."""
    loop = get_loop()
    box: dict[str, Any] = {}
    completed = False

    def on_success(result: Any) -> None:
        nonlocal completed
        box["result"], box["error"] = result, None
        completed = True
        loop.quit()

    def on_error(error: Exception) -> None:
        nonlocal completed
        box["result"], box["error"] = None, error
        completed = True
        loop.quit()

    timeout_handle = loop.call_later(timeout_sec, loop.quit)
    start(on_success, on_error)
    # Skip the loop if a callback already fired synchronously; an early quit() is forgotten.
    if not completed:
        loop.run()
    timeout_handle.cancel()
    assert completed, "operation did not finish before timeout"
    return box["result"], box["error"]
