"""MIME association lookup per the freedesktop mime-apps spec.

Replaces Gio.AppInfo.get_recommended_for_type / get_default_for_type /
get_default_for_uri_scheme: reads mimeapps.list (user config first) and the
distro-generated mimeinfo.cache files. Used for "Open with..." listings and
for opening URIs with their registered handler - notably remote locations
(smb://, sftp://, ...) where the handler is a file manager that mounts the
share itself.
"""

from __future__ import annotations

import configparser
import logging
import os
from typing import Iterator

from ulauncher import paths
from ulauncher.utils.desktop_app import DesktopApp

logger = logging.getLogger(__name__)

REMOTE_FS_SCHEMES = ("smb", "sftp", "ftp", "ftps", "dav", "davs", "nfs", "afp", "mtp", "gphoto2")


def _read_list_file(path: str) -> configparser.RawConfigParser | None:
    parser = configparser.RawConfigParser(delimiters=("=",), strict=False, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment, method-assign] - mime types are case-sensitive keys
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            parser.read_file(f)
    except (OSError, configparser.Error):
        return None
    return parser


def _split_ids(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split(";")) if item]


def _mimeapps_files() -> Iterator[str]:
    config_home = paths.XDG_CONFIG_HOME
    config_dirs = os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(os.pathsep)
    desktops = [d.lower() for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d]
    for base in [config_home, *config_dirs]:
        for desktop in desktops:
            yield os.path.join(base, f"{desktop}-mimeapps.list")
        yield os.path.join(base, "mimeapps.list")
    # Deprecated but still written by some tools
    for data_dir in [paths.XDG_DATA_HOME, *paths.XDG_DATA_DIRS]:
        yield os.path.join(data_dir, "applications", "mimeapps.list")


def _mimeinfo_cache_ids(mime: str) -> list[str]:
    ids: list[str] = []
    for data_dir in [paths.XDG_DATA_HOME, *paths.XDG_DATA_DIRS]:
        cache = _read_list_file(os.path.join(data_dir, "applications", "mimeinfo.cache"))
        if cache and cache.has_option("MIME Cache", mime):
            ids.extend(_split_ids(cache.get("MIME Cache", mime)))
    return ids


def _resolve(app_id: str) -> DesktopApp | None:
    return DesktopApp.new(app_id)


def default_app_for(mime: str) -> DesktopApp | None:
    """The default handler for a mime type (or x-scheme-handler/<scheme>), per spec:
    the first [Default Applications] entry that resolves, then the first association."""
    removed: set[str] = set()
    added: list[str] = []
    for list_path in _mimeapps_files():
        parser = _read_list_file(list_path)
        if parser is None:
            continue
        if parser.has_option("Default Applications", mime):
            for app_id in _split_ids(parser.get("Default Applications", mime)):
                if app_id in removed:
                    continue
                app = _resolve(app_id)
                if app is not None:
                    return app
        if parser.has_option("Removed Associations", mime):
            removed.update(_split_ids(parser.get("Removed Associations", mime)))
        if parser.has_option("Added Associations", mime):
            added.extend(a for a in _split_ids(parser.get("Added Associations", mime)) if a not in removed)
    for app_id in [*added, *(a for a in _mimeinfo_cache_ids(mime) if a not in removed)]:
        app = _resolve(app_id)
        if app is not None:
            return app
    return None


def recommended_apps_for(mime: str) -> list[DesktopApp]:
    """All applications associated with a mime type, default first, deduped."""
    removed: set[str] = set()
    ordered: list[str] = []
    for list_path in _mimeapps_files():
        parser = _read_list_file(list_path)
        if parser is None:
            continue
        for section in ("Default Applications", "Added Associations"):
            if parser.has_option(section, mime):
                ordered.extend(_split_ids(parser.get(section, mime)))
        if parser.has_option("Removed Associations", mime):
            removed.update(_split_ids(parser.get("Removed Associations", mime)))
    ordered.extend(_mimeinfo_cache_ids(mime))

    apps: list[DesktopApp] = []
    seen: set[str] = set()
    for app_id in ordered:
        if app_id in seen or app_id in removed:
            continue
        seen.add(app_id)
        app = _resolve(app_id)
        if app is not None:
            apps.append(app)
    return apps


def content_type_of(path: str) -> str:
    """Best-effort content type for a local path."""
    if os.path.isdir(path):
        return "inode/directory"
    try:
        from PySide6.QtCore import QMimeDatabase

        mime = QMimeDatabase().mimeTypeForFile(path)
        if mime.isValid():
            return mime.name()
    except ImportError:
        pass
    import mimetypes

    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def handler_for_uri(uri: str) -> DesktopApp | None:
    """The app registered to open a non-file URI, falling back to the default file
    manager for remote filesystem schemes (it mounts the share itself)."""
    scheme = uri.split(":", 1)[0].lower() if ":" in uri else ""
    if not scheme:
        return None
    handler = default_app_for(f"x-scheme-handler/{scheme}")
    if handler is None and scheme in REMOTE_FS_SCHEMES:
        handler = default_app_for("inode/directory")
    return handler
