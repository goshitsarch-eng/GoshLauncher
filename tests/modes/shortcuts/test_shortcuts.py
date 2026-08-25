from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ulauncher.modes.shortcuts.shortcuts import Shortcut


class TestShortcut:
    def test_coerces_legacy_icon_path(self) -> None:
        shortcut = Shortcut(icon="/media/google-search-icon.svg")

        assert shortcut.icon == "/icons/google-search.svg"

    def test_folds_user_icon_path(self) -> None:
        shortcut = Shortcut(icon=str(Path.home() / "icons" / "custom.png"))

        assert shortcut.icon == "~/icons/custom.png"

    def test_converts_legacy_float_timestamp(self) -> None:
        # Shortcut.__setitem__ coerces this to int, so the declared field type is narrower than the input.
        legacy: dict[str, Any] = {"added": 123.5}
        shortcut = Shortcut(**legacy)

        assert shortcut.added == 123


def test_first_run_does_not_seed_web_keyword_shortcuts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.data._file_cache import _get_or_create_instance
    from ulauncher.modes.shortcuts.shortcuts import Shortcuts

    monkeypatch.setattr("ulauncher.modes.shortcuts.shortcuts.paths.CONFIG", str(tmp_path))
    _get_or_create_instance.cache_clear()
    shortcuts = Shortcuts.load()
    assert dict(shortcuts) == {}
    assert not (tmp_path / "shortcuts.json").exists()


def test_stock_web_shortcuts_are_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from ulauncher.data._file_cache import _get_or_create_instance
    from ulauncher.modes.shortcuts.shortcuts import Shortcuts

    monkeypatch.setattr("ulauncher.modes.shortcuts.shortcuts.paths.CONFIG", str(tmp_path))
    (tmp_path / "shortcuts.json").write_text(
        json.dumps(
            {
                "googlesearch": {
                    "id": "googlesearch",
                    "keyword": "g",
                    "name": "Google Search",
                    "cmd": "https://google.com/search?q=%s",
                },
                "mine": {"id": "mine", "keyword": "zz", "name": "Mine", "cmd": "echo hi"},
            }
        )
    )
    _get_or_create_instance.cache_clear()
    shortcuts = Shortcuts.load()
    assert "googlesearch" not in shortcuts
    assert shortcuts["mine"].keyword == "zz"
