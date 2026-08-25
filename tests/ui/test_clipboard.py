from __future__ import annotations

from pathlib import Path

import pytest

from tests.ui.conftest import GTK4_AVAILABLE

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")


def test_clipboard_helper_uses_gtk46_set_content() -> None:
    source = Path(__file__).resolve().parents[2] / "ulauncher" / "ui" / "gtk4.py"
    text = source.read_text()
    assert "ContentProvider.new_for_bytes" in text
    assert "set_content" in text
    assert "clipboard.set(text)" not in text


def test_clipboard_set_text_does_not_raise() -> None:
    from gi.repository import Gdk

    from ulauncher.ui.gtk4 import clipboard_set_text

    if Gdk.Display.get_default() is None:
        pytest.skip("no Gdk display")
    clipboard_set_text("4")


def test_accelerator_label_parses_gtk4_control_space() -> None:
    from ulauncher.ui.gtk4 import accelerator_label

    label = accelerator_label("<Control>space")
    assert label
    assert "space" in label.lower()
