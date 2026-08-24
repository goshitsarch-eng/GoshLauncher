from __future__ import annotations

from ulauncher.modes.launcher.ime import ime_panel_visible, is_ime_panel_window
from ulauncher.modes.launcher.windows import WindowInfo


def _win(**kwargs: object) -> WindowInfo:
    values = {"wid": "0x1", "title": "", "wm_class": "", "desktop": 0, **kwargs}
    return WindowInfo(
        wid=str(values["wid"]),
        title=str(values["title"]),
        wm_class=str(values["wm_class"]),
        desktop=int(values["desktop"]),  # type: ignore[arg-type]
        app_id=str(values.get("app_id") or ""),
    )


def test_ibus_and_fcitx_candidate_windows_count_as_panels() -> None:
    assert is_ime_panel_window(_win(wm_class="ibus-ui-gtk3")) is True
    assert is_ime_panel_window(_win(app_id="org.freedesktop.IBus.Panel")) is True
    assert is_ime_panel_window(_win(title="Fcitx Candidate", wm_class="fcitx")) is True
    assert is_ime_panel_window(_win(wm_class="firefox", title="Mozilla Firefox")) is False
    assert is_ime_panel_window(_win(wm_class="ibus-setup", title="IBus Preferences")) is False


def test_ime_panel_visible_uses_supplied_window_list() -> None:
    hidden = [_win(wm_class="foot", title="Terminal")]
    shown = [_win(wm_class="ibus-ui-gtk4", title="")]
    assert ime_panel_visible(windows=hidden) is False
    assert ime_panel_visible(windows=shown) is True
