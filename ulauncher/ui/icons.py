"""Icon resolution for QML: theme icons by name, absolute paths, extension icons.

QML requests images as image://appicon/<icon-spec>?selected=0|1 where icon-spec is
an icon name or an absolute/~ path. Resolution order matches the old GTK logic:
file path -> icon theme -> mime-style fallbacks -> bundled executable.png.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtQuick import QQuickImageProvider

from ulauncher import paths

logger = logging.getLogger(__name__)

DEFAULT_EXE_ICON = f"{paths.ASSETS}/icons/executable.png"


def _themed(name: str) -> QIcon | None:
    icon = QIcon.fromTheme(name)
    return icon if not icon.isNull() else None


def resolve_icon(icon: str) -> QIcon:
    if not icon:
        icon = "application-x-executable"
    if icon.startswith("~"):
        icon = os.path.expanduser(icon)
    if icon.startswith("/"):
        if os.path.isfile(icon):
            file_icon = QIcon(icon)
            if not file_icon.isNull():
                return file_icon
        return QIcon(DEFAULT_EXE_ICON)

    themed = _themed(icon)
    if themed is None and "." in icon:
        # icon names like "org.kde.dolphin.png" - retry without the extension
        themed = _themed(icon.rsplit(".", 1)[0])
    if themed is None and "-" in icon:
        # mime-style names ("text-x-python") degrade to their generic class ("text-x-generic")
        themed = _themed(icon.split("-")[0] + "-x-generic") or _themed(icon.split("-")[0])
    if themed is None:
        themed = _themed("unknown") or _themed("application-x-executable")
    if themed is not None:
        return themed
    return QIcon(DEFAULT_EXE_ICON)


class AppIconProvider(QQuickImageProvider):
    NAME = "appicon"

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:  # noqa: N802
        from urllib.parse import unquote

        icon_name = unquote(icon_id)
        px = requested_size.width() if requested_size.isValid() and requested_size.width() > 0 else 32
        try:
            pixmap = resolve_icon(icon_name).pixmap(px, px)
        except Exception:
            logger.exception("Could not load icon %s", icon_name)
            pixmap = QPixmap(px, px)
            pixmap.fill(Qt.GlobalColor.transparent)
        if pixmap.isNull():
            pixmap = QPixmap(px, px)
            pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap
