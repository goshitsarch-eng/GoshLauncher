from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def clipboard_set_text(text: str) -> None:
    """Copy text to both the clipboard and the primary selection."""
    from PySide6.QtGui import QClipboard, QGuiApplication

    clipboard = QGuiApplication.clipboard()
    clipboard.setText(text, QClipboard.Mode.Clipboard)
    if clipboard.supportsSelection():
        clipboard.setText(text, QClipboard.Mode.Selection)
