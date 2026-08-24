from __future__ import annotations

from ulauncher.modes.launcher.osk import (
    OSK_WATCHES,
    PHOSH_OSK_DEST,
    PHOSH_OSK_IFACE,
    PROPERTIES_IFACE,
    OskWatcher,
    next_osk_watch_action,
    osk_keyboard_for_work_area,
    osk_visible_from_properties_changed,
)
from ulauncher.modes.launcher.popup_position import work_area_avoiding_keyboard


def test_next_osk_watch_action() -> None:
    assert next_osk_watch_action(False, True) == "start"
    assert next_osk_watch_action(True, False) == "stop"
    assert next_osk_watch_action(True, True) == "keep"


def test_osk_keyboard_shrinks_work_area_from_the_bottom() -> None:
    work = {"x": 0.0, "y": 0.0, "width": 1920.0, "height": 1080.0}
    hidden = osk_keyboard_for_work_area(work, False)
    assert work_area_avoiding_keyboard(work, hidden) == work
    shown = osk_keyboard_for_work_area(work, True, height=300)
    avoided = work_area_avoiding_keyboard(work, shown)
    assert avoided["height"] == 780
    assert shown["y"] == 780
    third = osk_keyboard_for_work_area(work, True)
    assert third["height"] == 360


def test_osk_visible_from_properties_changed() -> None:
    assert (
        osk_visible_from_properties_changed(
            PROPERTIES_IFACE,
            "PropertiesChanged",
            (PHOSH_OSK_IFACE, {"Visible": True}, []),
        )
        is True
    )
    assert (
        osk_visible_from_properties_changed(
            PROPERTIES_IFACE,
            "PropertiesChanged",
            (PHOSH_OSK_IFACE, {"Visible": False}, []),
        )
        is False
    )
    assert osk_visible_from_properties_changed(PROPERTIES_IFACE, "PropertiesChanged", (PHOSH_OSK_IFACE, {}, [])) is None
    assert (
        osk_visible_from_properties_changed("org.gnome.Shell", "PropertiesChanged", ("org.gnome.Shell", {}, [])) is None
    )
    assert OSK_WATCHES[0][0] == PHOSH_OSK_DEST


def test_osk_watcher_repositions_and_never_closes() -> None:
    changed: list[bool] = []
    subs: list[tuple[str, str, str, str]] = []

    def subscribe(dest: str, path: str, iface: str, member: str, _cb: object) -> int:
        subs.append((dest, path, iface, member))
        return len(subs)

    watcher = OskWatcher(changed.append, subscribe=subscribe, visible_probe=lambda: False)
    watcher.start()
    assert watcher.listening is True
    assert watcher.visible is False
    assert subs == list(OSK_WATCHES)
    watcher.start()
    assert len(subs) == 1
    watcher._on_signal(PROPERTIES_IFACE, "PropertiesChanged", (PHOSH_OSK_IFACE, {"Visible": True}, []))
    assert changed == [True]
    assert watcher.visible is True
    watcher._on_signal(PROPERTIES_IFACE, "PropertiesChanged", (PHOSH_OSK_IFACE, {"Visible": True}, []))
    assert changed == [True]
    watcher.stop()
    assert watcher.listening is False
