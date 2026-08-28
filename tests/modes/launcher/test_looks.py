from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.looks import (
    LOOKS,
    apply_look_chrome,
    chrome_from_settings,
    ensure_look_chrome,
    get_look,
    icon_size_for_look,
    look_about_subtitle,
    look_apply_action,
    look_ids,
    look_prefs_search_text,
    search_icon_style_class,
    should_apply_look,
)


def test_applied_look_defaults_empty_so_first_enable_stamps() -> None:
    from ulauncher.utils.settings import Settings

    assert Settings.applied_look == ""


# Spotlight-goshos themes.js look catalog (id, title, hint, chrome). Width is not a field.
GOSHOS_LOOKS = (
    ("spotlight", "Spotlight", "Search apps...", "center", "comfortable", False, True, True, True, True, "default", 28),
    ("omarchy", "Omarchy", "Search...", "center", "comfortable", False, True, True, True, True, "default", 24),
    ("popos", "Pop!_OS", "Type to search", "top", "comfortable", True, True, True, True, True, "windows-first", 36),
    ("ulauncher", "Ulauncher", "Search", "center", "comfortable", False, False, True, True, True, "default", 40),
    ("krunner", "KRunner", "Search or run", "top", "compact", True, False, True, True, True, "default", 20),
    ("gnome", "GNOME", "Type to search", "center", "comfortable", False, True, True, True, True, "default", 28),
    ("rofi", "Rofi", "Filter", "center", "compact", False, False, False, False, False, "default", 22),
    (
        "raycast",
        "Raycast",
        "Search for apps and commands...",
        "center",
        "comfortable",
        False,
        False,
        True,
        True,
        True,
        "default",
        32,
    ),
    ("albert", "Albert", "Enter a query", "center", "comfortable", False, True, True, True, True, "default", 26),
    ("wofi", "Wofi", "Search", "center", "compact", False, False, False, False, False, "default", 22),
    ("fuzzel", "Fuzzel", "Type to search", "center", "compact", False, False, False, True, False, "default", 24),
    ("anyrun", "Anyrun", "Search", "center", "comfortable", False, False, False, True, False, "default", 28),
    ("tofi", "Tofi", "Run", "top", "compact", False, False, False, False, False, "default", 20),
    ("light", "Light", "Type to search", "center", "comfortable", False, True, True, True, True, "default", 28),
    (
        "powertoys",
        "PowerToys",
        "Type here to search",
        "center",
        "comfortable",
        True,
        False,
        True,
        True,
        True,
        "default",
        32,
    ),
    ("synapse", "Synapse", "Search...", "center", "comfortable", False, False, True, True, False, "default", 48),
    ("onagre", "Onagre", "Search", "center", "comfortable", False, False, True, True, False, "default", 30),
)


def test_seventeen_looks_match_goshos_themes() -> None:
    ids = look_ids()
    assert ids == [row[0] for row in GOSHOS_LOOKS]
    assert len(ids) == 17
    assert get_look("missing")["id"] == LOOKS[0]["id"]
    for look, expected in zip(LOOKS, GOSHOS_LOOKS):
        (
            look_id,
            title,
            hint,
            position,
            density,
            numbers,
            headers,
            search_icon,
            result_icons,
            descriptions,
            order,
            icon,
        ) = expected
        chrome = look["look"]
        assert look["id"] == look_id
        assert look["title"] == title
        assert look["hint"] == hint
        assert chrome == {
            "position": position,
            "density": density,
            "show_numbers": numbers,
            "show_headers": headers,
            "show_search_icon": search_icon,
            "show_result_icons": result_icons,
            "show_descriptions": descriptions,
            "result_order": order,
            "icon_size": icon,
        }
        assert "width" not in chrome
        assert "base_width" not in chrome


def test_apply_look_chrome_stamps_popos() -> None:
    settings = SimpleNamespace(look_id="spotlight", applied_look="spotlight")
    apply_look_chrome(settings, "popos")
    assert settings.look_id == "popos"
    assert settings.applied_look == "popos"
    assert settings.popup_position == "top"
    assert settings.show_result_numbers is True
    assert settings.result_order == "windows-first"
    chrome = chrome_from_settings(settings)
    assert chrome["position"] == "top"
    assert chrome["show_numbers"] is True
    assert chrome["result_order"] == "windows-first"
    wide = SimpleNamespace(look_id="spotlight", applied_look="spotlight", base_width=800)
    payload = apply_look_chrome(wide, "krunner")
    assert wide.base_width == 800
    assert "base_width" not in payload
    assert "width" not in payload


def test_look_apply_action_stamps_default_without_rewriting_chrome() -> None:
    assert look_apply_action("spotlight", "") == "stamp"
    assert look_apply_action("popos", "") == "apply"
    assert look_apply_action("spotlight", "spotlight") == "keep"
    assert look_apply_action("popos", "spotlight") == "apply"
    assert should_apply_look("spotlight", "spotlight") is False
    assert should_apply_look("spotlight", "popos") is True
    stamped = SimpleNamespace(look_id="spotlight", applied_look="", icon_size=48)
    ensure_look_chrome(stamped)
    assert stamped.applied_look == "spotlight"
    assert stamped.icon_size == 48
    applied = SimpleNamespace(look_id="popos", applied_look="")
    ensure_look_chrome(applied)
    assert applied.applied_look == "popos"
    assert applied.popup_position == "top"


def test_search_icon_style_class_and_compact_icon_size() -> None:
    assert search_icon_style_class(True) == ""
    assert search_icon_style_class(False) == "gosh-no-search-icon"
    gnome = get_look("gnome")
    assert "session accent" in gnome["description"]
    assert "Dark Adwaita" in gnome["description"]
    assert "GNOME 47+" in gnome["description"]
    light = get_look("light")
    assert "session accent" in light["description"]
    assert "GNOME 47+" in light["description"]
    assert icon_size_for_look({"icon_size": 40}, "compact") == 32
    assert icon_size_for_look({"icon_size": 28}, "comfortable") == 28
    assert icon_size_for_look(get_look("popos")["look"], "comfortable") > icon_size_for_look(
        get_look("krunner")["look"], "comfortable"
    )
    assert icon_size_for_look(get_look("popos")["look"], "compact") > icon_size_for_look(
        get_look("krunner")["look"], "compact"
    )
    assert icon_size_for_look(get_look("synapse")["look"], "comfortable") > icon_size_for_look(
        get_look("powertoys")["look"], "comfortable"
    )
    assert icon_size_for_look(get_look("raycast")["look"], "comfortable") > icon_size_for_look(
        get_look("albert")["look"], "comfortable"
    )


def test_look_prefs_search_text_finds_walker_cosmic_and_titles() -> None:
    text = look_prefs_search_text()
    assert "Walker" in text
    assert "COSMIC" in text
    assert "Dark Adwaita" in text
    for look in LOOKS:
        assert look["title"] in text
    assert "Width is not part of a look" in text


def test_look_about_subtitle_matches_goshos() -> None:
    text = look_about_subtitle()
    assert "Walker" in text
    assert "COSMIC" in text
    assert "Dark Adwaita" not in text
    for look in LOOKS:
        assert look["title"] in text
