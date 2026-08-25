from __future__ import annotations

from ulauncher.modes.launcher.settings_panels import (
    match_settings_panels,
    settings_argv,
    settings_panel_available,
    settings_panel_desktop,
    settings_result_meta,
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
    unfiltered = match_settings_panels("wellbeing")
    assert unfiltered
    assert unfiltered[0]["id"] == "wellbeing"


def test_settings_result_is_not_activatable_without_launcher() -> None:
    panel = {"id": "wifi", "title": "Wi-Fi", "icon": "network-wireless-symbolic", "keywords": []}
    missing = settings_result_meta(panel, None)
    assert missing["activatable"] is False
    ready = settings_result_meta(panel, ["gnome-control-center", "wifi"])
    assert ready["activatable"] is True
    assert ready["id"] == "wifi"
    assert settings_argv("wifi", find_in_path=lambda _name: None) is None
    assert settings_argv("appearance", find_in_path=lambda name: name if name == "gio" else None) == [
        "gio",
        "launch",
        "gnome-background-panel.desktop",
    ]


# Catalog order from spotlight-goshos settingsPanels.js (Version 2026.08.20).
GOSHOS_SETTINGS_PANEL_IDS = [
    "wifi",
    "network",
    "wwan",
    "bluetooth",
    "display",
    "sound",
    "power",
    "multitasking",
    "background",
    "notifications",
    "search",
    "applications",
    "privacy",
    "online-accounts",
    "sharing",
    "wellbeing",
    "keyboard",
    "mouse",
    "wacom",
    "color",
    "printers",
    "universal-access",
    "users",
    "region",
    "datetime",
    "about",
    "system",
]


def test_settings_icons_are_symbolic() -> None:
    from ulauncher.modes.launcher.settings_panels import SETTINGS_PANELS

    assert SETTINGS_PANELS[0]["icon"] == "network-wireless-symbolic"
    assert all(str(panel["icon"]).endswith("-symbolic") for panel in SETTINGS_PANELS)


def test_settings_panel_catalog_matches_goshos() -> None:
    from ulauncher.modes.launcher.settings_panels import SETTINGS_PANELS

    assert [panel["id"] for panel in SETTINGS_PANELS] == GOSHOS_SETTINGS_PANEL_IDS
    assert len(SETTINGS_PANELS) == 27
    by_id = {panel["id"]: panel for panel in SETTINGS_PANELS}
    assert by_id["background"]["title"] == "Appearance"
    assert by_id["privacy"]["title"] == "Privacy & Security"
    assert by_id["universal-access"]["title"] == "Accessibility"


def test_goshos_settings_aliases() -> None:
    expected = (
        ("winver", "about"),
        ("dnd", "notifications"),
        ("hotspot", "wifi"),
        ("hot", "wifi"),
        ("wireless", "wifi"),
        ("a11y", "universal-access"),
        ("zoom", "universal-access"),
        ("camera", "privacy"),
        ("location", "privacy"),
        ("microphone", "privacy"),
        ("thunderbolt", "privacy"),
        ("firmware", "privacy"),
        ("security", "privacy"),
        ("user-accounts", "users"),
        ("info-overview", "about"),
        ("stylus", "wacom"),
        ("fractional scaling", "display"),
    )
    for query, panel_id in expected:
        assert any(panel["id"] == panel_id for panel in match_settings_panels(query)), query
    assert any(panel["id"] == "online-accounts" for panel in match_settings_panels("o", 20))
    assert not any(panel["id"] == "wifi" for panel in match_settings_panels("o", 20))
    assert not any(panel["id"] == "wifi" for panel in match_settings_panels("pot"))
    assert not any(panel["id"] == "wifi" for panel in match_settings_panels("ifi"))


def test_empty_settings_query_slices_unfiltered_catalog() -> None:
    rows = match_settings_panels("", 5)
    assert [panel["id"] for panel in rows] == GOSHOS_SETTINGS_PANEL_IDS[:5]
    assert len(match_settings_panels("", 8)) == 8
