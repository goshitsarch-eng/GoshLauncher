"""QML list model over the core's Result lists."""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from ulauncher.internals.result import Result
from ulauncher.modes.launcher.result_row import number_hint
from ulauncher.modes.launcher.selection_math import is_selectable_result
from ulauncher.utils.fuzzy_search import get_matching_blocks

ROLE_NAME = Qt.ItemDataRole.UserRole + 1
ROLE_DESCRIPTION = Qt.ItemDataRole.UserRole + 2
ROLE_ICON = Qt.ItemDataRole.UserRole + 3
ROLE_COMPACT = Qt.ItemDataRole.UserRole + 4
ROLE_IS_HEADER = Qt.ItemDataRole.UserRole + 5
ROLE_SELECTABLE = Qt.ItemDataRole.UserRole + 6
ROLE_NUMBER_HINT = Qt.ItemDataRole.UserRole + 7
ROLE_RICH_NAME = Qt.ItemDataRole.UserRole + 8
ROLE_WRAP = Qt.ItemDataRole.UserRole + 9


def highlight_markup(query_str: str, text: str) -> str:
    """The result name as rich text with fuzzy-matched characters emboldened."""
    escaped_full = html.escape(text)
    if not query_str or not text:
        return escaped_full
    blocks, _score = get_matching_blocks(query_str, text)
    if not blocks:
        return escaped_full
    out: list[str] = []
    cursor = 0
    for index, chars in blocks:
        out.append(html.escape(text[cursor:index]))
        out.append("<b>" + html.escape(chars) + "</b>")
        cursor = index + len(chars)
    out.append(html.escape(text[cursor:]))
    return "".join(out)


def _is_header(result: Result) -> bool:
    return not result.highlightable and not result.actions and result.compact


class ResultsModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._results: list[Result] = []
        self._query_str = ""

    # Python-side accessors

    @property
    def results(self) -> list[Result]:
        return self._results

    def result_at(self, row: int) -> Result | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def set_results(self, results: list[Result], query_str: str, append: bool = False) -> None:
        if append and self._results:
            first = len(self._results)
            self.beginInsertRows(QModelIndex(), first, first + len(results) - 1)
            self._results.extend(results)
            self.endInsertRows()
            return
        self.beginResetModel()
        self._results = list(results)
        self._query_str = query_str
        self.endResetModel()

    def selectable_indexes(self) -> list[int]:
        return [i for i, r in enumerate(self._results) if is_selectable_result(r)]

    # QAbstractListModel interface

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._results)

    def roleNames(self) -> dict[int, Any]:
        return {
            ROLE_NAME: b"name",
            ROLE_DESCRIPTION: b"description",
            ROLE_ICON: b"icon",
            ROLE_COMPACT: b"compact",
            ROLE_IS_HEADER: b"isHeader",
            ROLE_SELECTABLE: b"selectable",
            ROLE_NUMBER_HINT: b"numberHint",
            ROLE_RICH_NAME: b"richName",
            ROLE_WRAP: b"wrap",
        }

    def data(self, index: QModelIndex, role: int = ROLE_NAME) -> Any:
        row = index.row()
        if not index.isValid() or not 0 <= row < len(self._results):
            return None
        result = self._results[row]
        if role == ROLE_NAME:
            return result.name
        if role == ROLE_DESCRIPTION:
            return "" if result.compact else result.description
        if role == ROLE_ICON:
            return result.icon or ""
        if role == ROLE_COMPACT:
            return result.compact
        if role == ROLE_IS_HEADER:
            return _is_header(result)
        if role == ROLE_SELECTABLE:
            return is_selectable_result(result)
        if role == ROLE_NUMBER_HINT:
            hint_index = self._hint_index(row)
            return number_hint(hint_index, True) if hint_index is not None else ""
        if role == ROLE_RICH_NAME:
            if result.highlightable:
                highlight_input = result.get_highlightable_input(self._query_str)
                return highlight_markup(highlight_input, result.name)
            return html.escape(result.name)
        if role == ROLE_WRAP:
            return result.wrap
        return None

    def _hint_index(self, row: int) -> int | None:
        """Position of this row among the highlightable rows (headers excluded), or None."""
        if not self._results[row].highlightable:
            return None
        count = 0
        for i, result in enumerate(self._results):
            if i == row:
                return count
            if result.highlightable:
                count += 1
        return None
