"""Light/dark handling for the Qt UI.

Default is "system": the platform theme (Breeze on KDE, the qt5ct/qt6ct or
platformtheme choice elsewhere) supplies the palette, so the app follows the
desktop's color scheme live - Kirigami.Theme derives everything from it.
"light"/"dark" force a scheme via QStyleHints where available (Qt >= 6.8),
falling back to a hand-built palette.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VALID_SCHEMES = ("system", "light", "dark")


def _forced_palette(dark: bool) -> object:
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    if dark:
        base = QColor(35, 38, 41)  # Breeze dark values
        alt = QColor(49, 54, 59)
        text = QColor(252, 252, 252)
        highlight = QColor(61, 174, 233)
    else:
        base = QColor(255, 255, 255)
        alt = QColor(239, 240, 241)
        text = QColor(35, 38, 41)
        highlight = QColor(61, 174, 233)
    palette.setColor(QPalette.ColorRole.Window, alt)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, alt)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(252, 252, 252))
    palette.setColor(QPalette.ColorRole.ToolTipBase, alt)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(text.red(), text.green(), text.blue(), 128))
    return palette


def apply_color_scheme(scheme: str) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QPalette

    app = QGuiApplication.instance()
    if app is None:
        return
    if scheme not in VALID_SCHEMES:
        scheme = "system"

    hints = app.styleHints()
    set_scheme = getattr(hints, "setColorScheme", None)
    if callable(set_scheme):  # Qt >= 6.8
        mapping = {
            "system": Qt.ColorScheme.Unknown,
            "light": Qt.ColorScheme.Light,
            "dark": Qt.ColorScheme.Dark,
        }
        try:
            set_scheme(mapping[scheme])
        except (TypeError, ValueError):
            logger.debug("setColorScheme failed; falling back to palette override", exc_info=True)
        else:
            return

    if scheme == "system":
        app.setPalette(QPalette())
    else:
        app.setPalette(_forced_palette(scheme == "dark"))
