from __future__ import annotations

from ulauncher.modes.launcher.global_shortcuts import (
    SHORTCUT_ID,
    activated_shortcut_id,
    bind_shortcuts_entries,
    gtk_accel_to_portal_trigger,
    portal_request_path,
    portal_sender_token,
    session_handle_from_response,
    should_bind_portal,
    should_toggle_for_activation,
)


def test_gtk_accel_to_portal_trigger_maps_ctrl_space() -> None:
    assert gtk_accel_to_portal_trigger("<Control>space") == "CTRL+SPACE"
    assert gtk_accel_to_portal_trigger("<Primary>space") == "CTRL+SPACE"
    assert gtk_accel_to_portal_trigger("<Control><Shift>space") == "CTRL+SHIFT+SPACE"
    assert gtk_accel_to_portal_trigger("<Super>space") == "SUPER+SPACE"
    assert gtk_accel_to_portal_trigger("<Alt>F2") == "ALT+F2"


def test_portal_is_used_when_the_desktop_has_no_keybinding_store() -> None:
    assert should_bind_portal("GNOME") is False
    assert should_bind_portal("XFCE") is False
    assert should_bind_portal("PLASMA") is False
    assert should_bind_portal("HYPRLAND") is True
    assert should_bind_portal("SWAY") is True
    assert should_bind_portal("niri") is True
    assert should_bind_portal("COSMIC") is True


def test_portal_request_path_strips_unique_name_punctuation() -> None:
    assert portal_sender_token(":1.42") == "1_42"
    assert portal_request_path(":1.42", "ulab") == "/org/freedesktop/portal/desktop/request/1_42/ulab"


def test_session_handle_and_activation_parse_portal_payloads() -> None:
    assert session_handle_from_response(0, {"session_handle": "/s/1"}) == "/s/1"
    assert session_handle_from_response(1, {"session_handle": "/s/1"}) == ""
    assert session_handle_from_response(0, {}) == ""
    assert activated_shortcut_id(("/s", SHORTCUT_ID, 0, {})) == SHORTCUT_ID
    assert activated_shortcut_id(("/s", SHORTCUT_ID)) == SHORTCUT_ID
    assert should_toggle_for_activation(SHORTCUT_ID) is True
    assert should_toggle_for_activation("other") is False


def test_bind_shortcuts_entries_use_preferred_trigger() -> None:
    entries = bind_shortcuts_entries("CTRL+SPACE")
    assert entries[0][0] == SHORTCUT_ID
    assert entries[0][1]["preferred_trigger"] == "CTRL+SPACE"
    assert entries[0][1]["description"] == "Show GoshLauncher"
