from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.popup_gate import (
    TIME_LIMITS_REACHED,
    can_open_popup,
    close_teardown_order,
    destroy_teardown_order,
    next_open_error_action,
    next_reopen_after_close,
    next_toggle_action,
    popup_open_entry_text,
    run_isolated_teardown,
    session_limits_reached,
    should_cancel_open_on_overview,
    should_cancel_open_on_shell_ui,
    should_close_on_overview,
    should_close_on_session,
    should_close_on_shell_ui,
    should_close_on_toggle,
    should_keep_query_on_close,
    should_schedule_close,
    should_schedule_open,
    time_limits_state,
)


def test_open_always_clears_the_entry_like_goshos() -> None:
    assert popup_open_entry_text() == ""
    assert should_keep_query_on_close(True, True) is False
    assert should_keep_query_on_close(False, False) is False


def test_popup_gate_open_and_toggle_actions() -> None:
    assert can_open_popup(False, False, False, False) is True
    assert can_open_popup(True, False, False, False) is False
    assert can_open_popup(False, True, False, False) is False
    assert can_open_popup(False, False, True, False) is False
    assert can_open_popup(False, False, False, True) is False
    assert can_open_popup(False, False, False, False, True) is False
    assert next_open_error_action(True, False) == "close"
    assert next_open_error_action(False, True) == "close"
    assert next_open_error_action(False, False) == "keep"
    order = close_teardown_order()
    assert ",".join(order[:4]) == "mark-closed,hide,hide-backdrop,release-unredirect"
    assert order.index("hide-backdrop") < order.index("release-unredirect")
    assert order.index("hide") < order.index("disconnect-host")
    destroy = destroy_teardown_order()
    assert destroy.index("unlisten-hosts") < destroy.index("close")


def test_isolated_teardown_keeps_going_after_throw() -> None:
    calls: list[str] = []

    def _session() -> None:
        calls.append("session")
        message = "session"
        raise RuntimeError(message)

    finished = run_isolated_teardown(
        [
            _session,
            lambda: calls.append("close"),
            lambda: calls.append("chrome"),
        ]
    )
    assert calls == ["session", "close", "chrome"]
    assert finished == 2


def test_session_limits_and_toggle_reopen() -> None:
    assert session_limits_reached(TIME_LIMITS_REACHED) is True
    assert session_limits_reached(0) is False
    assert time_limits_state(None) == 0
    assert time_limits_state(SimpleNamespace(state=TIME_LIMITS_REACHED)) == TIME_LIMITS_REACHED
    assert should_close_on_toggle(True, False) is True
    assert should_close_on_toggle(False, True) is True
    assert should_close_on_toggle(False, False) is False
    assert next_reopen_after_close(False, False) is False
    assert next_reopen_after_close(True, False) is True
    assert next_reopen_after_close(True, True) is False
    assert next_toggle_action(False, False, False, False) == "open"
    assert next_toggle_action(False, False, True, False) == "cancel-open"
    assert next_toggle_action(True, False, False, False) == "close"
    assert next_toggle_action(False, True, False, False) == "close"
    assert next_toggle_action(True, False, False, True) == "toggle-reopen"
    assert next_toggle_action(False, False, True, True) == "toggle-reopen"
    assert should_close_on_session(True, False) is True
    assert should_close_on_session(False, True) is True
    assert should_close_on_session(False, False) is False
    assert should_close_on_session(False, False, True) is True
    assert should_cancel_open_on_overview(True) is True
    assert should_cancel_open_on_overview(False) is False
    assert should_close_on_overview(True, False) is True
    assert should_close_on_overview(False, True) is True
    assert should_close_on_overview(False, False) is False
    assert should_cancel_open_on_shell_ui(True) is True
    assert should_close_on_shell_ui(True, False) is True
    assert should_close_on_shell_ui(False, False) is False


def test_open_and_close_are_scheduled_once() -> None:
    assert should_schedule_open(False, False, False) is True
    assert should_schedule_open(True, False, False) is False
    assert should_schedule_open(False, True, False) is False
    assert should_schedule_open(False, False, True) is False
    assert should_schedule_close(False) is True
    assert should_schedule_close(True) is False
