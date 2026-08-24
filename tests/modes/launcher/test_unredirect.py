from __future__ import annotations

from ulauncher.modes.launcher.unredirect import (
    gtk_unredirect_backend,
    hyprland_getoption_argv,
    hyprland_hold_argv,
    hyprland_restore_argv,
    hyprland_session_active,
    mutter_hold_write,
    next_unredirect_action,
    parse_hyprland_scanout,
    unredirect_api,
)


def test_unredirect_api_and_hold_release() -> None:
    assert unredirect_api(True, True) == "compositor"
    assert unredirect_api(False, True) == "display"
    assert unredirect_api(False, False) == ""
    assert next_unredirect_action(False, True, "compositor") == "hold"
    assert next_unredirect_action(True, True, "compositor") == "keep"
    assert next_unredirect_action(True, False, "compositor") == "release"
    assert next_unredirect_action(False, False, "compositor") == "keep"
    assert next_unredirect_action(False, True, "") == "keep"


def test_gtk_backends_prefer_mutter_then_hyprland() -> None:
    assert gtk_unredirect_backend(True, True) == "mutter-gsettings"
    assert gtk_unredirect_backend(False, True) == "hyprland"
    assert gtk_unredirect_backend(False, False) == ""
    assert next_unredirect_action(False, True, "mutter-gsettings") == "hold"
    assert next_unredirect_action(True, False, "hyprland") == "release"
    assert mutter_hold_write() is False


def test_hyprland_session_and_scanout_argv() -> None:
    assert hyprland_session_active(env={}, which=lambda _name: "/usr/bin/hyprctl") is False
    assert hyprland_session_active(env={"HYPRLAND_INSTANCE_SIGNATURE": "x"}, which=lambda _name: None) is False
    assert hyprland_session_active(env={"HYPRLAND_INSTANCE_SIGNATURE": "x"}, which=lambda _name: "/usr/bin/hyprctl")
    assert hyprland_getoption_argv() == ["hyprctl", "-j", "getoption", "render:direct_scanout"]
    assert hyprland_hold_argv() == ["hyprctl", "keyword", "render:direct_scanout", "0"]
    assert hyprland_restore_argv("1") == ["hyprctl", "keyword", "render:direct_scanout", "1"]
    assert hyprland_restore_argv("")[-1] == "2"
    assert parse_hyprland_scanout('{"int": 1}') == "1"
    assert parse_hyprland_scanout({"str": "2"}) == "2"
    assert parse_hyprland_scanout("") == "2"
    assert parse_hyprland_scanout("0") == "0"
