"""Arrow wrap and page-key clamp, ported from spotlight-goshos selectionMath.js."""

from __future__ import annotations

from typing import Any, Sequence


def next_selected_index(current: int, delta: int, length: int) -> int:
    if length == 0:
        return -1
    nxt = current + delta
    if abs(delta) == 1:
        if nxt < 0:
            return length - 1
        if nxt >= length:
            return 0
        return nxt
    if nxt < 0:
        return 0
    if nxt >= length:
        return length - 1
    return nxt


def is_selectable_result(result: Any) -> bool:
    """Whether the arrow keys may land on this row.

    Result is a dict subclass, so the dict branch has to apply the same three checks as the
    attribute branch. Reading only `activatable` made section headers selectable, which put the
    first highlight on a section title and, with more than one section, left every row after the
    second header unreachable: the move landed on the header index and ResultsView snapped it
    back to the first row.
    """
    if result is None:
        return False
    if isinstance(result, dict):
        activatable = result.get("activatable", True)
        highlightable = result.get("highlightable", True)
        actions = result.get("actions")
    else:
        activatable = getattr(result, "activatable", True)
        highlightable = getattr(result, "highlightable", True)
        actions = getattr(result, "actions", None)
    if activatable is False or highlightable is False:
        return False
    return not (isinstance(actions, dict) and not actions)


def next_activatable_index(current: int, delta: int, results: Sequence[Any]) -> int:
    length = len(results)
    if length == 0:
        return -1

    if abs(delta) == 1:
        nxt = current
        for _ in range(length):
            nxt += delta
            if nxt < 0:
                nxt = length - 1
            elif nxt >= length:
                nxt = 0
            if is_selectable_result(results[nxt]):
                return nxt
        return current if 0 <= current < length and is_selectable_result(results[current]) else -1

    nxt = next_selected_index(current, delta, length)
    if nxt < 0:
        return -1
    if is_selectable_result(results[nxt]):
        return nxt

    step = 1 if delta > 0 else -1
    index = nxt + step
    while 0 <= index < length:
        if is_selectable_result(results[index]):
            return index
        index += step
    index = nxt - step
    while 0 <= index < length:
        if is_selectable_result(results[index]):
            return index
        index -= step
    return -1
