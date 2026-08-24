"""Goshos ``resultRow.js``: digit hints ``1``…``9`` when numbers are on."""

from __future__ import annotations

from typing import Optional

# goshos: ``showNumbers && resultIndex < 9`` then ``String(resultIndex + 1)``
NUMBER_HINT_LIMIT = 9
SELECTED_STYLE_CLASS = "selected"
# goshos resultRow.js St.BoxLayout spacing; look CSS owns padding
RESULT_CHILD_SPACING = 12


def number_hint(result_index: int, show_numbers: bool) -> Optional[str]:
    if show_numbers and 0 <= result_index < NUMBER_HINT_LIMIT:
        return str(result_index + 1)
    return None
