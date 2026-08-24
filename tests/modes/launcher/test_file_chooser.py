from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.file_chooser import chooser_selected_path, should_take_chooser_path


def test_chooser_selected_path_prefers_gio_file() -> None:
    chooser = SimpleNamespace(get_file=lambda: SimpleNamespace(get_path=lambda: "/tmp/icon.png"))
    assert chooser_selected_path(chooser) == "/tmp/icon.png"


def test_chooser_selected_path_falls_back_to_filename() -> None:
    chooser = SimpleNamespace(get_file=lambda: None, get_filename=lambda: "/tmp/icon.svg")
    assert chooser_selected_path(chooser) == "/tmp/icon.svg"


def test_chooser_selected_path_none_for_missing_local_path() -> None:
    chooser = SimpleNamespace(get_file=lambda: SimpleNamespace(get_path=lambda: None), get_filename=lambda: None)
    assert chooser_selected_path(chooser) is None


def test_should_take_chooser_path() -> None:
    assert should_take_chooser_path(0, 0) is True
    assert should_take_chooser_path(-1, 0) is False
