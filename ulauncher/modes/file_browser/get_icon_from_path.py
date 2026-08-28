import mimetypes
import os
from pathlib import Path

from ulauncher.utils.user_dirs import get_user_dir

SPECIAL_DIRS = {
    get_user_dir("DOWNLOAD"): "folder-download",
    get_user_dir("DOCUMENTS"): "folder-documents",
    get_user_dir("MUSIC"): "folder-music",
    get_user_dir("PICTURES"): "folder-pictures",
    get_user_dir("PUBLICSHARE"): "folder-publicshare",
    get_user_dir("TEMPLATES"): "folder-templates",
    get_user_dir("VIDEOS"): "folder-videos",
    get_user_dir("DESKTOP"): "user-desktop",
    Path("~").expanduser().as_posix(): "folder-home",
}


def get_icon_from_path(path: str, is_dir: bool) -> str:
    if is_dir:
        return SPECIAL_DIRS.get(path) or "folder"

    if mime := mimetypes.guess_type(Path(path).name)[0]:
        return mime.replace("/", "-")

    if os.access(path, os.X_OK):
        return "application-x-executable"

    return "unknown"
