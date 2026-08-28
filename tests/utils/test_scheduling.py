"""Behavior tests for scheduling on the MiniLoop backend (no Qt in test processes)."""

from unittest.mock import Mock

import pytest

from tests.utils.loop_helpers import process_pending_events
from ulauncher.utils import scheduling


class TestContext:
    def test_cancel_is_idempotent(self) -> None:
        context = scheduling.timer(60, Mock())
        assert context.active
        context.cancel()
        context.cancel()
        assert not context.active

    def test_run_once_forwards_arguments(self) -> None:
        func = Mock()
        context = scheduling.Context(func, False, ("a", "b"), {"kw": "v"})
        assert context._run_once() is False
        func.assert_called_once_with("a", "b", kw="v")

    def test_run_once_signals_continuation_when_repeating(self) -> None:
        func = Mock()
        context = scheduling.Context(func, True, (), {})
        assert context._run_once() is True
        func.assert_called_once_with()

    def test_run_once_signals_removal_when_func_cancels_a_repeating_schedule(self) -> None:
        context = scheduling.Context(Mock(), True, (), {})
        context._func = context.cancel
        assert context._run_once() is False
        assert not context.active

    def test_run_once_logs_and_contains_func_errors(self, caplog: pytest.LogCaptureFixture) -> None:
        context = scheduling.Context(Mock(side_effect=RuntimeError("boom")), False, (), {})
        assert context._run_once() is False
        assert not context.active
        assert "Unhandled error in scheduled call" in caplog.text

    def test_run_once_keeps_repeating_schedule_alive_when_func_raises(self) -> None:
        context = scheduling.Context(Mock(side_effect=RuntimeError("boom")), True, (), {})
        assert context._run_once() is True
        assert context.active

    def test_run_once_does_not_run_func_after_cancel(self) -> None:
        func = Mock()
        context = scheduling.Context(func, False, (), {})
        context.cancel()
        assert context._run_once() is False
        func.assert_not_called()

    def test_stop_when_ends_a_repeating_schedule(self) -> None:
        context = scheduling.Context(Mock(), True, (), {}, stop_when=lambda: True)
        assert context._run_once() is False
        assert not context.active


class TestTimer:
    def test_fires_once(self) -> None:
        func = Mock()
        scheduling.timer(0.01, func, "a", kw="v")
        process_pending_events(0.1)
        func.assert_called_once_with("a", kw="v")

    def test_cancel_prevents_firing(self) -> None:
        func = Mock()
        context = scheduling.timer(0.01, func)
        context.cancel()
        process_pending_events(0.1)
        func.assert_not_called()


class TestInterval:
    def test_fires_repeatedly_until_cancelled(self) -> None:
        calls: list[int] = []
        context = scheduling.interval(0.01, lambda: calls.append(1))
        process_pending_events(0.08)
        context.cancel()
        count = len(calls)
        assert count >= 2
        process_pending_events(0.05)
        assert len(calls) == count

    def test_survives_a_raising_run(self) -> None:
        calls: list[int] = []

        def flaky() -> None:
            calls.append(1)
            if len(calls) == 1:
                msg = "boom"
                raise RuntimeError(msg)

        context = scheduling.interval(0.01, flaky)
        process_pending_events(0.08)
        context.cancel()
        assert len(calls) >= 2


class TestRunWhenIdle:
    def test_runs_soon(self) -> None:
        func = Mock()
        scheduling.run_when_idle(func, 1, kw=2)
        process_pending_events(0.05)
        func.assert_called_once_with(1, kw=2)

    def test_is_thread_safe(self) -> None:
        import threading

        func = Mock()
        thread = threading.Thread(target=lambda: scheduling.run_when_idle(func))
        thread.start()
        thread.join()
        process_pending_events(0.05)
        func.assert_called_once_with()
