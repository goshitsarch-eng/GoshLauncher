"""Scheduling helpers that dispatch callbacks onto the application's main loop.

Two backends share one public API:

- The app process runs the Qt event loop, so timers become ``QTimer`` and fd
  watches become ``QSocketNotifier``. Everything is marshalled to the Qt main
  thread, which keeps the old contract that scheduled work always runs on the
  UI thread (``run_when_idle`` is the documented way to get there from other
  threads).
- Extension client processes never import Qt; they run the dependency-free
  ``ulauncher.utils.eventloop.MiniLoop`` instead.

The backend is picked per call: Qt when PySide6 is already imported and a
QCoreApplication exists, MiniLoop otherwise. The app creates its
QApplication before any scheduling happens, extensions never create one, so
the choice is stable in practice.
"""

from __future__ import annotations

import logging
import select
import sys
import threading
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")

logger = logging.getLogger(__name__)

_qt_dispatcher: Any = None
_qt_dispatcher_lock = threading.Lock()


def _qt_core() -> Any:
    """The PySide6.QtCore module when Qt drives this process's main loop, else None.

    Checks sys.modules rather than importing, so extension processes never pay
    for (or require) a Qt import.
    """
    qt_core = sys.modules.get("PySide6.QtCore")
    if qt_core is not None and qt_core.QCoreApplication.instance() is not None:
        return qt_core
    return None


def _get_qt_dispatcher() -> Any:
    """A QObject living in the Qt main thread; its signal queues closures onto it."""
    global _qt_dispatcher  # noqa: PLW0603
    with _qt_dispatcher_lock:
        if _qt_dispatcher is None:
            qt_core = _qt_core()

            class _Dispatcher(qt_core.QObject):  # type: ignore[misc]
                submit = qt_core.Signal(object)

                def __init__(self) -> None:
                    super().__init__()
                    self.submit.connect(self._run)

                def _run(self, closure: Callable[[], None]) -> None:
                    closure()

            dispatcher = _Dispatcher()
            dispatcher.moveToThread(qt_core.QCoreApplication.instance().thread())
            _qt_dispatcher = dispatcher
    return _qt_dispatcher


def _on_qt_main_thread() -> bool:
    qt_core = _qt_core()
    app = qt_core.QCoreApplication.instance()
    return qt_core.QThread.currentThread() is app.thread()


class Context:
    """
    Handle for a scheduled callback.

    Cancel it with .cancel(), which is idempotent and safe to call after the
    callback has already fired.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        repeat: bool,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        stop_when: Callable[[], bool] | None = None,
    ) -> None:
        self._func = func
        self._repeat = repeat
        self._args = args
        self._kwargs = kwargs
        self._stop_when = stop_when
        self._cancelled = False
        self._cleanup: Callable[[], None] | None = None

    def cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        cleanup, self._cleanup = self._cleanup, None
        if cleanup is not None:
            qt_core = _qt_core()
            if qt_core is not None and not _on_qt_main_thread():
                _get_qt_dispatcher().submit.emit(cleanup)
            else:
                cleanup()

    @property
    def active(self) -> bool:
        return not self._cancelled

    def _run_once(self) -> bool:
        """Invoke the callback behind an exception barrier; returns whether to keep repeating.

        Raising into the event loop would bypass our logging and kill a repeating
        schedule, so contain errors here - an interval survives a bad run.
        """
        if self._cancelled:
            return False
        try:
            self._func(*self._args, **self._kwargs)
        except Exception:
            logger.exception("Unhandled error in scheduled call to %s", getattr(self._func, "__qualname__", self._func))
        keep_alive = self._repeat and not self._cancelled
        if keep_alive and self._stop_when is not None and self._stop_when():
            keep_alive = False
        if not keep_alive:
            self._cancelled = True
        return keep_alive


def _schedule_qt_timer(context: Context, delay_sec: float) -> None:
    qt_core = _qt_core()

    def _setup() -> None:
        if context._cancelled:  # noqa: SLF001
            return
        timer = qt_core.QTimer()
        timer.setTimerType(qt_core.Qt.TimerType.PreciseTimer)
        timer.setInterval(int(delay_sec * 1000))

        def _fire() -> None:
            if not context._run_once():  # noqa: SLF001
                timer.stop()
                context._cleanup = None  # noqa: SLF001

        timer.timeout.connect(_fire)
        context._cleanup = timer.stop  # noqa: SLF001 - keeps the QTimer referenced too
        timer.start()

    if _on_qt_main_thread():
        _setup()
    else:
        _get_qt_dispatcher().submit.emit(_setup)


def _schedule_qt_fd_watch(context: Context, fd: int) -> None:
    qt_core = _qt_core()

    def _setup() -> None:
        if context._cancelled:  # noqa: SLF001
            return
        notifier = qt_core.QSocketNotifier(fd, qt_core.QSocketNotifier.Type.Read)

        def _fire() -> None:
            if not context._run_once():  # noqa: SLF001
                notifier.setEnabled(False)
                context._cleanup = None  # noqa: SLF001

        notifier.activated.connect(_fire)
        context._cleanup = lambda: notifier.setEnabled(False)  # noqa: SLF001

    if _on_qt_main_thread():
        _setup()
    else:
        _get_qt_dispatcher().submit.emit(_setup)


def _schedule_miniloop(context: Context, delay_sec: float, interval_sec: float | None) -> None:
    from ulauncher.utils.eventloop import get_loop

    loop = get_loop()

    def _fire() -> None:
        if not context._run_once():
            handle.cancel()
            context._cleanup = None

    handle = loop.call_later(delay_sec, _fire, interval=interval_sec)
    context._cleanup = handle.cancel


def _schedule_miniloop_fd(context: Context, fd: int) -> None:
    from ulauncher.utils.eventloop import get_loop

    loop = get_loop()

    def _fire() -> None:
        if not context._run_once():
            loop.unwatch_fd(fd)
            context._cleanup = None

    loop.watch_fd(fd, _fire)
    context._cleanup = lambda: loop.unwatch_fd(fd)


def timer(delay_sec: float, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> Context:
    """
    Runs func once after delay_sec seconds, in the main loop thread.

    func is called with the provided positional and keyword arguments. For example:
        timer(0.5, myfunc, arg1, arg2, kw=val)

    Returns a Context with a .cancel() method.
    """
    context = Context(func, False, args, kwargs)
    if _qt_core() is not None:
        _schedule_qt_timer(context, delay_sec)
    else:
        _schedule_miniloop(context, delay_sec, None)
    return context


def interval(delay_sec: float, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> Context:
    """
    Runs func every delay_sec seconds, in the main loop thread.

    func is called with the provided positional and keyword arguments. For example:
        interval(0.5, myfunc, arg1, arg2, kw=val)

    Returns a Context with a .cancel() method.
    """
    context = Context(func, True, args, kwargs)
    if _qt_core() is not None:
        _schedule_qt_timer(context, delay_sec)
    else:
        _schedule_miniloop(context, delay_sec, delay_sec)
    return context


def fd_is_hung_up(fd: int) -> bool:
    """Whether fd is closed, errored, or its peer hung up. A closed fd counts as hung up."""
    poller = select.poll()
    try:
        poller.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
        events = poller.poll(0)
    except (OSError, ValueError):
        return True
    return any(event & (select.POLLHUP | select.POLLERR | select.POLLNVAL) for _fd, event in events)


def watch_fd(fd: int, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> Context:
    """
    Runs func on the main loop thread whenever fd is readable, hung up, or in error.

    The watch stops itself once the fd hangs up. A hung-up fd stays permanently ready, so a
    repeating source over one is re-dispatched as fast as the main loop can spin - a peer
    restart otherwise pins a core for the rest of the session. func still runs for that last
    dispatch, so the watcher sees the EOF before the watch goes away.
    """
    context = Context(func, True, args, kwargs, stop_when=lambda: fd_is_hung_up(fd))
    if _qt_core() is not None:
        _schedule_qt_fd_watch(context, fd)
    else:
        _schedule_miniloop_fd(context, fd)
    return context


def run_when_idle(func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> Context:
    """
    Runs func as soon as the main loop is idle, in the main loop thread.

    This is also the supported way to hop from a worker thread onto the main thread.

    func is called with the provided positional and keyword arguments. For example:
        run_when_idle(myfunc, arg1, arg2, kw=val)

    Returns a Context with a .cancel() method.
    """
    context = Context(func, False, args, kwargs)
    if _qt_core() is not None:
        _schedule_qt_timer(context, 0.0)
    else:
        _schedule_miniloop(context, 0.0, None)
    return context
