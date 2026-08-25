from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.ui.conftest import GTK4_AVAILABLE
from ulauncher.modes.launcher.looks import look_ids
from ulauncher.ui.helpers.theme import CSS_RESET, launcher_popup_css

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")

if GTK4_AVAILABLE:
    from tests.ui.look_paint import (
        close_popup_window,
        css_parsing_errors,
        display_available,
        open_popup_window,
        sample_entry_selection,
        sample_look,
        sample_placeholder,
        sample_popup_look,
    )

# Spotlight-goshos stylesheet / README panel fills. Spotlight's .app is transparent;
# the pill (.prompt) is rgb(28, 28, 30) / #1c1c1e.
LOOK_PANEL_HEX = {
    "spotlight": "#1c1c1e",
    "omarchy": "#1a1b26",
    "popos": "#242426",
    "ulauncher": "#2b2b2b",
    "krunner": "#2a2e32",
    "gnome": "#303030",
    "rofi": "#111111",
    "raycast": "#161618",
    "albert": "#31363b",
    "wofi": "#1d1f21",
    "fuzzel": "#fdf6e3",
    "anyrun": "#1e1e2e",
    "tofi": "#000000",
    "light": "#f6f5f4",
    "powertoys": "#2c2c2c",
    "synapse": "#3c3b37",
    "onagre": "#1c1917",
}

# Opaque selected-row fills. Looks that use rgba overlays are sampled in CSS, not pixels.
LOOK_SELECTED_HEX = {
    "krunner": "#3daee9",
    "gnome": "#3584e4",
    "rofi": "#005577",
    "raycast": "#3a3a3e",
    "albert": "#1d99f3",
    "wofi": "#285577",
    "fuzzel": "#eee8d5",
    "tofi": "#ffffff",
    "light": "#3584e4",
    "powertoys": "#0078d4",
    "onagre": "#f59e0b",
}

# Opaque goshos StLabel.hint-text colors. Spotlight/Pop!_OS/Ulauncher/KRunner/GNOME use rgba.
LOOK_PLACEHOLDER_HEX = {
    "omarchy": "#565f89",
    "rofi": "#666666",
    "raycast": "#6e6e73",
    "albert": "#7f8c8d",
    "wofi": "#707880",
    "fuzzel": "#93a1a1",
    "anyrun": "#6c7086",
    "tofi": "#888888",
    "light": "#9a9996",
    "powertoys": "#9a9a9a",
    "synapse": "#a39e93",
    "onagre": "#78716c",
}

_PIXEL_TOLERANCE = 3
_PLACEHOLDER_TOLERANCE = 8


def _hex_rgb(value: str) -> tuple[int, int, int]:
    hex_color = value.lstrip("#")
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _near(actual: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = _PIXEL_TOLERANCE) -> bool:
    return all(abs(part - want) <= tolerance for part, want in zip(actual, expected))


def test_css_reset_is_gtk4() -> None:
    assert "-icon-shadow" not in CSS_RESET


def test_look_css_uses_gtk4_properties() -> None:
    text = (Path(__file__).resolve().parents[2] / "data" / "themes" / "gosh-looks.css").read_text()
    assert "selection-background-color" not in text
    assert "max-height:" not in text
    assert "text-align:" not in text
    assert "icon-size:" not in text.replace("-gtk-icon-size:", "")
    assert ".input selection {" in text
    for look_id in look_ids():
        if look_id == "spotlight":
            continue
        assert f".gosh-theme-{look_id} .input selection" in text


def test_launcher_popup_css_parses_on_gtk4() -> None:
    errors = css_parsing_errors(launcher_popup_css())
    assert errors == []


@pytest.mark.parametrize("look_id", look_ids())
def test_look_panel_pixels(look_id: str) -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    sampled = sample_look(look_id)
    expected = _hex_rgb(LOOK_PANEL_HEX[look_id])
    assert _near(sampled["panel"], expected), f"{look_id} panel {sampled['panel']} != {expected}"
    selected_hex = LOOK_SELECTED_HEX.get(look_id)
    if selected_hex:
        selected_expected = _hex_rgb(selected_hex)
        assert _near(sampled["selected"], selected_expected), (
            f"{look_id} selected {sampled['selected']} != {selected_expected}"
        )


@pytest.fixture(scope="module")
def popup_window() -> Iterator[object]:
    if not GTK4_AVAILABLE:
        pytest.skip("GTK 4 is not available")
    if not display_available():
        pytest.skip("no Gdk display")
    try:
        win = open_popup_window()
    except (RuntimeError, TypeError, OSError) as exc:
        pytest.skip(f"could not open launcher popup: {exc}")
    yield win
    close_popup_window()


def test_popup_window_is_gosh_popup_and_snapshots(popup_window: object) -> None:
    win = popup_window
    assert win.has_css_class("gosh-popup")
    assert "gosh-theme-" in " ".join(win.theme_root.get_css_classes())
    _width, height = win.get_default_size()
    assert height != 1
    assert win.prompt.get_width() > 40
    assert win.prompt.get_height() > 1
    rgb = sample_popup_look("omarchy")
    assert _near(rgb["panel"], _hex_rgb(LOOK_PANEL_HEX["omarchy"])), rgb
    assert not hasattr(win, "prefs_btn")


@pytest.mark.parametrize("look_id", look_ids())
def test_popup_look_panel_pixels(popup_window: object, look_id: str) -> None:
    assert popup_window.has_css_class("gosh-popup")  # type: ignore[union-attr]
    sampled = sample_popup_look(look_id)
    expected = _hex_rgb(LOOK_PANEL_HEX[look_id])
    assert _near(sampled["panel"], expected), f"{look_id} popup panel {sampled['panel']} != {expected}"
    selected_hex = LOOK_SELECTED_HEX.get(look_id)
    if selected_hex:
        selected_expected = _hex_rgb(selected_hex)
        assert _near(sampled["selected"], selected_expected), (
            f"{look_id} popup selected {sampled['selected']} != {selected_expected}"
        )


def test_entry_selection_paints_tofi_highlight() -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    rgb = sample_entry_selection("tofi")
    expected = _hex_rgb("#555555")
    assert _near(rgb, expected, 24), f"tofi entry selection {rgb} != {expected}"


@pytest.mark.parametrize("look_id", sorted(LOOK_PLACEHOLDER_HEX))
def test_look_placeholder_pixels(look_id: str) -> None:
    if not display_available():
        pytest.skip("no Gdk display")
    expected = _hex_rgb(LOOK_PLACEHOLDER_HEX[look_id])
    rgb = sample_placeholder(look_id, expected)
    assert _near(rgb, expected, _PLACEHOLDER_TOLERANCE), f"{look_id} placeholder {rgb} != {expected}"
