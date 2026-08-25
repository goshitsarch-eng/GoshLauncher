"""Pick a row that can run, ported from spotlight-goshos resultActivate.js."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _field(result: Any, name: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def result_can_activate(result: Any) -> bool:
    if result is None:
        return False
    if _field(result, "activatable", True) is False:
        return False
    activate = _field(result, "activate")
    if callable(activate):
        return True
    return bool(_field(result, "actions"))


def activatable_result(results: list[Any], selected_index: int) -> Any | None:
    if 0 <= selected_index < len(results) and result_can_activate(results[selected_index]):
        return results[selected_index]
    for result in results:
        if result_can_activate(result):
            return result
    return None


def indexed_activatable_result(results: list[Any], index: int) -> Any | None:
    if 0 <= index < len(results) and result_can_activate(results[index]):
        return results[index]
    return None


def activate_result_safe(result: Any) -> bool:
    try:
        activate = _field(result, "activate")
        if not callable(activate):
            return False
        activate()
    except Exception:
        # mutter and systemactions throw if the target vanished after the list
        return False
    return True


def activate_popup_result(
    result: Any,
    close: Callable[[], None],
    activate: Callable[[Any, bool], Any],
    alt: bool = False,
) -> bool:
    """Hide first, then run the row — goshos launcherPopup.activateResult.

    Alt keeps the popup open so leftover Ulauncher action lists can paint.
    """
    if not result_can_activate(result):
        return False
    if not alt:
        close()
    try:
        activate(result, alt)
    except Exception:
        # mutter and systemactions throw if the target vanished after the list
        return False
    return True
