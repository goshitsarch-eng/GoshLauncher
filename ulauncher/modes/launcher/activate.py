"""Pick a row that can run, ported from spotlight-goshos resultActivate.js."""

from __future__ import annotations

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
