from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.looks import LOOKS, apply_look_chrome, chrome_from_settings, get_look, look_ids


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


def test_every_look_has_theme_css() -> None:
    from pathlib import Path

    css_path = Path(__file__).resolve().parents[3] / "data" / "themes" / "gosh-looks.css"
    text = css_path.read_text()
    ids = look_ids()
    assert len(ids) == 17
    for look_id in ids:
        assert f".gosh-theme-{look_id}" in text
