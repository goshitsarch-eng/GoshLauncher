from __future__ import annotations

from ulauncher.modes.launcher.settings_panels import (
    match_settings_panels,
    settings_panel_available,
    settings_panel_desktop,
)


def test_wellbeing_desktop_id_matches_goshos() -> None:
    assert settings_panel_desktop("wellbeing") == "gnome-wellbeing-panel.desktop"
    assert settings_panel_desktop("appearance") == "gnome-background-panel.desktop"


def test_wellbeing_hidden_when_desktop_missing() -> None:
    assert settings_panel_available("wifi", has_desktop=lambda _i: False) is True
    assert settings_panel_available("wellbeing", has_desktop=lambda _i: False) is False
    assert settings_panel_available("wellbeing", has_desktop=lambda _i: True) is True
    hidden = match_settings_panels("wellbeing", is_available=lambda panel_id: panel_id != "wellbeing")
    assert hidden == []
    shown = match_settings_panels("wellbeing", is_available=lambda _panel_id: True)
    assert shown
    assert shown[0]["id"] == "wellbeing"
