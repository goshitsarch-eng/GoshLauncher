from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.system_modal import (
    SYSTEM_MODAL_BUS_NAMES,
    SYSTEM_MODAL_WATCHES,
    launcher_keyboard_mode,
    name_owner_changed_should_close,
)


def test_screenshot_name_appearing_closes_and_shell_screenshot_is_ignored() -> None:
    assert "org.gnome.Shell.Screenshot" not in SYSTEM_MODAL_BUS_NAMES
    assert name_owner_changed_should_close("org.gnome.Screenshot", "", ":1.99") is True
    assert name_owner_changed_should_close("org.gnome.Snapshot", "", ":1.8") is True
    assert name_owner_changed_should_close("org.kde.Spectacle", "", ":1.12") is True
    assert name_owner_changed_should_close("org.xfce.Screenshooter", "", ":1.4") is True
    assert name_owner_changed_should_close("org.gnome.Screenshot", ":1.99", "") is False
    assert name_owner_changed_should_close("org.gnome.Screenshot", ":1.1", ":1.1") is False
    assert name_owner_changed_should_close("org.freedesktop.PolicyKit1", "", ":1.2") is False
    assert SYSTEM_MODAL_WATCHES[0][3] == "NameOwnerChanged"


def test_on_demand_keyboard_mode_falls_back_to_exclusive() -> None:
    on_demand = object()
    exclusive = object()
    both = SimpleNamespace(ON_DEMAND=on_demand, EXCLUSIVE=exclusive)
    assert launcher_keyboard_mode(both) is on_demand
    only_exclusive = SimpleNamespace(EXCLUSIVE=exclusive)
    assert launcher_keyboard_mode(only_exclusive) is exclusive
