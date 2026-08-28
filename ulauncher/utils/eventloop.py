"""Minimal callback event loop for processes without Qt (extension client processes).

The app process runs the Qt event loop; extension processes used to run a GLib
MainLoop. This replaces the latter with a dependency-free loop built on
``selectors`` + a timer heap, exposing just what ``ulauncher.utils.scheduling``
and ``ulauncher.api.socket_client`` need: one-shot/repeating timers, idle
callbacks, fd readability watches, and a thread-safe wakeup.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import os
import selectors
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

_counter = itertools.count()


class Handle:
    """Cancellation handle for a scheduled callback or fd watch."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _TimerEntry:
    __slots__ = ("callback", "due", "handle", "interval", "order")

    def __init__(self, due: float, callback: Callable[[], Any], interval: float | None) -> None:
        self.due = due
        self.callback = callback
        self.interval = interval  # None for one-shot, seconds for repeating
        self.handle = Handle()
        self.order = next(_counter)

    def __lt__(self, other: _TimerEntry) -> bool:
        return (self.due, self.order) < (other.due, other.order)


class MiniLoop:
    def __init__(self) -> None:
        self._selector = selectors.DefaultSelector()
        self._timers: list[_TimerEntry] = []
        self._running = False
        self._lock = threading.Lock()
        self._pending: list[_TimerEntry] = []  # entries added from other threads
        # Self-pipe so other threads can interrupt the poll
        self._wake_r, self._wake_w = os.pipe()
        os.set_blocking(self._wake_r, False)
        os.set_blocking(self._wake_w, False)
        self._selector.register(self._wake_r, selectors.EVENT_READ, self._drain_wakeup)
        self._thread_id: int | None = None

    def _drain_wakeup(self) -> None:
        try:
            while os.read(self._wake_r, 4096):
                pass
        except OSError:
            pass

    def _wakeup(self) -> None:
        try:
            os.write(self._wake_w, b"\0")
        except OSError:
            pass

    def call_later(self, delay_sec: float, callback: Callable[[], Any], interval: float | None = None) -> Handle:
        entry = _TimerEntry(time.monotonic() + max(delay_sec, 0.0), callback, interval)
        if self._thread_id in (None, threading.get_ident()):
            heapq.heappush(self._timers, entry)
        else:
            with self._lock:
                self._pending.append(entry)
            self._wakeup()
        return entry.handle

    def call_soon(self, callback: Callable[[], Any]) -> Handle:
        return self.call_later(0.0, callback)

    def watch_fd(self, fd: int, callback: Callable[[], Any]) -> Handle:
        """Invoke callback whenever fd is readable (includes EOF/HUP with select semantics)."""
        handle = Handle()

        def _dispatch() -> None:
            if handle.cancelled:
                self.unwatch_fd(fd)
                return
            callback()

        self._selector.register(fd, selectors.EVENT_READ, _dispatch)
        return handle

    def unwatch_fd(self, fd: int) -> None:
        try:
            self._selector.unregister(fd)
        except (KeyError, ValueError):
            pass

    def _pull_pending(self) -> None:
        if not self._pending:
            return
        with self._lock:
            entries, self._pending = self._pending, []
        for entry in entries:
            heapq.heappush(self._timers, entry)

    def _run_due_timers(self) -> float | None:
        """Run all due timers; return seconds until the next one (None if no timers)."""
        while True:
            self._pull_pending()
            if not self._timers:
                return None
            entry = self._timers[0]
            if entry.handle.cancelled:
                heapq.heappop(self._timers)
                continue
            now = time.monotonic()
            if entry.due > now:
                return entry.due - now
            heapq.heappop(self._timers)
            try:
                entry.callback()
            except Exception:
                logger.exception("Unhandled error in scheduled callback")
            if entry.interval is not None and not entry.handle.cancelled:
                entry.due = time.monotonic() + entry.interval
                entry.order = next(_counter)
                heapq.heappush(self._timers, entry)

    def run(self) -> None:
        self._running = True
        self._thread_id = threading.get_ident()
        # Adopt entries scheduled before the loop thread was known
        while self._running:
            timeout = self._run_due_timers()
            if not self._running:
                break
            for key, _mask in self._selector.select(timeout):
                callback = key.data
                try:
                    callback()
                except Exception:
                    logger.exception("Unhandled error in fd watch callback")
        self._thread_id = None

    def is_running(self) -> bool:
        return self._running

    def quit(self) -> None:
        self._running = False
        self._wakeup()


_loop: MiniLoop | None = None


def get_loop() -> MiniLoop:
    global _loop  # noqa: PLW0603
    if _loop is None:
        _loop = MiniLoop()
    return _loop
