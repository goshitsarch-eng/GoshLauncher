"""Keep combo rows in sync with settings, ported from Spotlight-goshos prefsCombo.js."""

from __future__ import annotations

from typing import Any, Sequence


def combo_selected_index(items: Sequence[Any], current_id: str | None) -> int:
    for index, item in enumerate(items):
        item_id = item["id"] if isinstance(item, dict) else getattr(item, "id", None)
        if item_id == current_id:
            return index
    return -1
