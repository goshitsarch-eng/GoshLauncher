"""Whether a shortcut should open or close, from spotlight-goshos popupGate.js."""

from __future__ import annotations

from typing import Any, Callable, Iterable

TIME_LIMITS_REACHED = 2


def session_limits_reached(state: Any) -> bool:
    return state == TIME_LIMITS_REACHED


def time_limits_state(manager: Any) -> int:
    if not manager:
        return 0
    if isinstance(manager, dict):
        return int(manager.get("state", 0) or 0)
    return int(getattr(manager, "state", 0) or 0)


def popup_open_entry_text() -> str:
    """goshos launcherPopup.open always does this._entry.set_text('')."""
    return ""


def should_keep_query_on_close(_save_query: bool = False, _auto_resume: bool = False) -> bool:
    """Leftover Ulauncher auto_resume. goshos never restores the previous query."""
    return False


def can_open_popup(
    is_open: bool,
    visible: bool,
    locked: bool,
    greeter: bool,
    limits_reached: bool = False,
) -> bool:
    return not is_open and not visible and not locked and not greeter and not limits_reached


def next_open_error_action(is_open: bool, visible: bool) -> str:
    if is_open or visible:
        return "close"
    return "keep"


def close_teardown_order() -> list[str]:
    return [
        "mark-closed",
        "hide",
        "hide-backdrop",
        "release-unredirect",
        "disconnect-host",
        "destroy-children",
        "clear-focus",
    ]


def destroy_teardown_order() -> list[str]:
    return ["clear-idles", "unlisten-hosts", "close", "release-unredirect", "remove-chrome"]


def run_isolated_teardown(steps: Iterable[Callable[[], None]]) -> int:
    finished = 0
    for step in steps:
        try:
            step()
        except Exception:  # noqa: S110
            pass
        else:
            finished += 1
    return finished


def should_close_on_session(locked: bool, greeter: bool, limits_reached: bool = False) -> bool:
    return locked or greeter or bool(limits_reached)


def should_close_on_toggle(is_open: bool, visible: bool) -> bool:
    return is_open or visible


def next_reopen_after_close(close_pending: bool, reopen_after_close: bool) -> bool:
    if not close_pending:
        return False
    return not reopen_after_close


def should_cancel_open_on_shell_ui(open_pending: bool) -> bool:
    return bool(open_pending)


def should_close_on_shell_ui(is_open: bool, visible: bool) -> bool:
    return is_open or visible


should_cancel_open_on_overview = should_cancel_open_on_shell_ui
should_close_on_overview = should_close_on_shell_ui


def next_toggle_action(is_open: bool, visible: bool, open_pending: bool, close_pending: bool) -> str:
    if close_pending:
        return "toggle-reopen"
    if open_pending:
        return "cancel-open"
    if is_open or visible:
        return "close"
    return "open"


def should_schedule_open(open_pending: bool, is_open: bool, visible: bool) -> bool:
    return not open_pending and not is_open and not visible


def should_schedule_close(close_pending: bool) -> bool:
    return not close_pending
