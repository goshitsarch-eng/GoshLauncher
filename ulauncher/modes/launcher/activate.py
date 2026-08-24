"""Pick a row that can run, ported from spotlight-goshos resultActivate.js."""

from __future__ import annotations

from typing import Any


def result_can_activate(result: Any) -> bool:
    if result is None:
        return False
    actions = getattr(result, "actions", None)
    return bool(actions)


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
