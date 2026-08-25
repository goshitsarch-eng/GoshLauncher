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


def test_seventeen_looks() -> None:
    ids = look_ids()
    assert len(ids) == 17
    assert "spotlight" in ids
    assert "popos" in ids
    assert get_look("missing")["id"] == LOOKS[0]["id"]
    pop = get_look("popos")
    assert pop["look"]["result_order"] == "windows-first"
    assert pop["look"]["show_numbers"] is True


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


def test_every_look_has_theme_css() -> None:
    from pathlib import Path

    css_path = Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css"
    text = css_path.read_text()
    ids = look_ids()
    assert len(ids) == 17
    for look_id in ids:
        assert f".gosh-theme-{look_id}" in text


def test_hidden_search_icon_inset_follows_goshos_order() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    compact = text.find(".app.gosh-density-compact .input")
    no_icon_20 = text.find(".app.gosh-no-search-icon .input {\n  padding-left: 20px;")
    compact_no = text.find(".app.gosh-density-compact.gosh-no-search-icon .input {\n  padding-left: 16px;")
    rofi = text.find(".app.gosh-theme-rofi.gosh-no-search-icon .input")
    assert compact != -1
    assert compact < no_icon_20 < compact_no < rofi
    leftover_16 = text.find(".app.gosh-no-search-icon .input {\n  padding-left: 16px;")
    assert leftover_16 == -1


def test_spotlight_shell_is_transparent_like_goshos() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    app_rule = text.split(".app {", 1)[1].split("}", 1)[0]
    assert "background-color: transparent" in app_rule
    assert "box-shadow: none" in app_rule
    assert "window," in text
    assert "window.background" in text
    omarchy = text.split(".gosh-theme-omarchy.app {", 1)[1].split("}", 1)[0]
    assert "#1a1b26" in omarchy
    popos = text.split(".gosh-theme-popos.app {", 1)[1].split("}", 1)[0]
    assert "#242426" in popos
