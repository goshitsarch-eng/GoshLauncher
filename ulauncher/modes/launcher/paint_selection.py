"""Keep the selected row across an async repaint, ported from spotlight-goshos paintSelection.js."""

from __future__ import annotations

from typing import Any, Sequence

from ulauncher.modes.launcher.selection_math import is_selectable_result


def _row_id(result: Any) -> Any:
    if isinstance(result, dict):
        value = result.get("id")
        return value if isinstance(value, (str, int)) and value != "" else None
    payload = getattr(result, "payload", None)
    if isinstance(payload, dict):
        value = payload.get("id")
        if isinstance(value, (str, int)) and value != "":
            return value
    value = getattr(result, "item_id", None)
    return value if isinstance(value, (str, int)) and value != "" else None


def _row_type(result: Any) -> str | None:
    if isinstance(result, dict):
        value = result.get("type")
        return value if isinstance(value, str) else None
    value = getattr(result, "kind", None) or getattr(result, "type", None)
    return value if isinstance(value, str) else None


def _row_title(result: Any) -> str | None:
    if isinstance(result, dict):
        # Result is a dict subclass whose display string is `name`, not `title`
        value = result.get("title")
        if not isinstance(value, str) or value == "":
            value = result.get("name")
        return value if isinstance(value, str) else None
    value = getattr(result, "name", None) or getattr(result, "title", None)
    return value if isinstance(value, str) else None


def _row_description(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("description")
        return value if isinstance(value, str) else ""
    value = getattr(result, "description", None)
    return value if isinstance(value, str) else ""


def result_selection_key(result: Any, index: int) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "type": _row_type(result),
        "title": _row_title(result),
        "description": _row_description(result),
        "id": _row_id(result),
        "index": index,
    }


def first_selectable_index(results: Sequence[Any]) -> int:
    if not results:
        return -1
    for index, result in enumerate(results):
        if is_selectable_result(result):
            return index
    return -1


def row_matches_previous(previous: Any, result: Any) -> bool:
    if previous is None or result is None:
        return False
    prev_id = previous.get("id") if isinstance(previous, dict) else _row_id(previous)
    if prev_id not in (None, ""):
        return _row_id(result) == prev_id
    prev_type = previous.get("type") if isinstance(previous, dict) else _row_type(previous)
    prev_title = previous.get("title") if isinstance(previous, dict) else _row_title(previous)
    if _row_type(result) != prev_type or _row_title(result) != prev_title:
        return False
    if prev_title in (None, ""):
        return False
    if isinstance(previous, dict) and "description" in previous:
        return _row_description(result) == (previous.get("description") or "")
    return True


def paint_selection_index(previous: Any, results: Sequence[Any]) -> int:
    if not results:
        return -1
    if not previous:
        return first_selectable_index(results)
    prev_id = previous.get("id") if isinstance(previous, dict) else _row_id(previous)
    if prev_id not in (None, ""):
        for index, result in enumerate(results):
            if _row_id(result) == prev_id and is_selectable_result(result):
                return index
    prev_type = previous.get("type") if isinstance(previous, dict) else _row_type(previous)
    prev_title = previous.get("title") if isinstance(previous, dict) else _row_title(previous)
    if isinstance(previous, dict):
        prev_desc = (previous.get("description") or "") if "description" in previous else None
    else:
        prev_desc = _row_description(previous)
    for index, result in enumerate(results):
        if not is_selectable_result(result):
            continue
        if _row_type(result) != prev_type or _row_title(result) != prev_title:
            continue
        if prev_desc is not None and _row_description(result) != prev_desc:
            continue
        return index
    prev_index = previous.get("index") if isinstance(previous, dict) else getattr(previous, "index", None)
    if isinstance(prev_index, int) and 0 <= prev_index < len(results) and is_selectable_result(results[prev_index]):
        return prev_index
    return first_selectable_index(results)
