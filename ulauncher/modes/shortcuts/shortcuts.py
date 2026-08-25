from __future__ import annotations

import re
from typing import Any

from ulauncher import paths
from ulauncher.data import BaseDataClass, JsonKeyValueConf
from ulauncher.utils.fold_user_path import fold_user_path

# First-run used to seed these. They steal `g query` from Spotlight-goshos (web last unless @).
_STOCK_WEB_SHORTCUT_CMDS = {
    "googlesearch": "https://google.com/search?q=%s",
    "stackoverflow": "https://stackoverflow.com/search?q=%s",
    "wikipedia": "https://en.wikipedia.org/wiki/%s",
}


class Shortcut(BaseDataClass):
    name: str = ""
    keyword: str = ""
    cmd: str = ""
    icon: str = ""
    is_default_search: bool = False
    run_without_argument: bool = False  # Only used in ShortcutTrigger (not Result)
    added: int = 0
    id: str = ""

    def __setitem__(self, key: str, value: Any) -> None:  # type: ignore[override]
        if key == "added" and isinstance(value, float):
            # convert legacy float timestamps ulauncher used
            value = int(value)

        # icon path has changed in v6, from /media/{google-search,stackoverflow,wikipedia}-icon.svg to /icons/*.svg
        if key == "icon" and isinstance(value, str):
            value = fold_user_path(value)
            value = re.sub(r"/media/(.*?)-icon", "/icons/\\1", value)
        super().__setitem__(key, value)


def is_stock_web_shortcut(shortcut_id: str, cmd: str) -> bool:
    return _STOCK_WEB_SHORTCUT_CMDS.get(shortcut_id) == cmd


class Shortcuts(JsonKeyValueConf[str, Shortcut]):
    @classmethod
    def load(cls) -> Shortcuts:  # type: ignore[override]
        file_path = f"{paths.CONFIG}/shortcuts.json"
        instance = super().load(file_path)
        dropped = [key for key, shortcut in instance.items() if is_stock_web_shortcut(key, shortcut.cmd)]
        if dropped:
            for key in dropped:
                del instance[key]
            instance.save()
        return instance
