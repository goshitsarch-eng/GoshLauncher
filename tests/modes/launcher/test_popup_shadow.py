from __future__ import annotations

from pathlib import Path

from ulauncher.modes.launcher.looks import look_ids
from ulauncher.modes.launcher.popup_shadow import (
    look_shadow_inset,
    origin_minus_inset,
    surface_size_with_inset,
)


def _looks_css() -> str:
    return (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()


def test_look_shadow_inset_follows_css_blur() -> None:
    css = _looks_css()
    assert look_shadow_inset(css, "spotlight") == 16
    assert look_shadow_inset(css, "omarchy") == 36
    assert look_shadow_inset(css, "popos") == 40
    assert look_shadow_inset(css, "raycast") == 48
    assert origin_minus_inset(157, 16) == 141
    assert surface_size_with_inset(600, 16) == 632
    for look_id in look_ids():
        assert look_shadow_inset(css, look_id) >= 16
