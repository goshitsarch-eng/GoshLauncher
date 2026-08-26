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


def test_every_look_has_theme_css() -> None:
    from pathlib import Path

    css_path = Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css"
    text = css_path.read_text()
    ids = look_ids()
    assert len(ids) == 17
    for look_id in ids:
        assert f".gosh-theme-{look_id}" in text
    assert "selection-background-color" not in text
    assert ".input selection {" in text


def test_hidden_search_icon_inset_follows_goshos_order() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    # the compact entry rule steps aside for the looks that are compact by definition
    compact = text.find(".app.gosh-density-compact:not(")
    no_icon_20 = text.find(".app.gosh-no-search-icon .input {\n  padding-left: 20px;")
    compact_no = text.find(".app.gosh-density-compact.gosh-no-search-icon .input {\n  padding-left: 16px;")
    rofi = text.find(".app.gosh-theme-rofi.gosh-no-search-icon .input")
    assert compact != -1
    assert compact < no_icon_20 < compact_no < rofi
    leftover_16 = text.find(".app.gosh-no-search-icon .input {\n  padding-left: 16px;")
    assert leftover_16 == -1


def test_compact_row_padding_comes_after_every_look() -> None:
    from pathlib import Path

    # goshos: compact .gosh-result is last so it beats theme padding. Omarchy/Anyrun
    # already reserve the 3px leading edge in their own .item-box blocks.
    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    compact = text.rfind(".app.gosh-density-compact .item-box")
    assert compact != -1
    for look_id in look_ids():
        theme_row = text.rfind(f".gosh-theme-{look_id} .item-box")
        if theme_row == -1:
            continue
        assert compact > theme_row, look_id
    assert "border-left: 3px solid transparent" in text
    assert "border-left-color: #7aa2f7" in text
    assert "border-left-color: #89b4fa" in text
    assert "caret-color: #ff6363" in text
    assert "caret-color: #60cdff" in text
    assert "caret-color: #f07746" in text
    assert "background-color: #000000" in text
    assert "background-color: #fdf6e3" in text
    assert "background-color: #1d99f3" in text
    assert "background-color: #285577" in text
    for look_id in (
        "omarchy",
        "popos",
        "ulauncher",
        "gnome",
        "raycast",
        "fuzzel",
        "anyrun",
        "powertoys",
        "synapse",
    ):
        assert f".gosh-theme-{look_id} .item-box.selected .item-descr" in text, look_id


def test_every_look_panel_fill_is_in_css() -> None:
    from pathlib import Path

    # Same fills as tests/ui/test_look_pixels.py LOOK_PANEL_HEX (goshos README).
    fills = {
        "spotlight": "rgb(28, 28, 30)",
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
    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    for look_id, color in fills.items():
        if look_id == "spotlight":
            block = text.split(".gosh-theme-spotlight .prompt {", 1)[1].split("}", 1)[0]
        else:
            block = text.split(f".gosh-theme-{look_id}.app {{", 1)[1].split("}", 1)[0]
        assert color in block, look_id


def test_spotlight_prompt_owns_the_pill_fill() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    block = text.split(".gosh-theme-spotlight .prompt {", 1)[1].split("}", 1)[0]
    assert "rgb(28, 28, 30)" in block
    results = text.split(".gosh-theme-spotlight .result-box {", 1)[1].split("}", 1)[0]
    assert "rgb(28, 28, 30)" in results


def test_spotlight_shell_is_transparent_like_goshos() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    app_rule = text.split(".app {", 1)[1].split("}", 1)[0]
    assert "background-color: transparent" in app_rule
    assert "box-shadow: none" in app_rule
    assert "window.gosh-popup" in text
    assert "window.gosh-popup.background" in text
    omarchy = text.split(".gosh-theme-omarchy.app {", 1)[1].split("}", 1)[0]
    assert "#1a1b26" in omarchy
    popos = text.split(".gosh-theme-popos.app {", 1)[1].split("}", 1)[0]
    assert "#242426" in popos


def test_look_placeholder_colors_match_goshos_hint_text() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    assert "rgba(245, 245, 247, 0.35)" in text
    hints = {
        "omarchy": "#565f89",
        "popos": "rgba(242, 242, 242, 0.4)",
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
    for look_id, color in hints.items():
        assert f".gosh-theme-{look_id} .input placeholder" in text
        assert f".gosh-theme-{look_id} .input text.placeholder {{\n  color: {color};\n}}" in text
    assert ".prefs-btn" not in text


def test_compact_entry_rule_leaves_the_compact_looks_their_own_type() -> None:
    from pathlib import Path

    # This rule outranks every `.gosh-theme-X .input` on specificity whatever the order, so
    # without the exclusions KRunner, Rofi, Wofi, Fuzzel and Tofi all rendered the same 16px
    # entry instead of the 14/15px each one declares.
    text = (Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css").read_text()
    rule = text[text.find(".app.gosh-density-compact:not(") :].split("{", 1)[0]
    for look_id in ("krunner", "rofi", "wofi", "fuzzel", "tofi"):
        assert f":not(\n    .gosh-theme-{look_id}\n  )" in rule or f":not(.gosh-theme-{look_id})" in rule, look_id
