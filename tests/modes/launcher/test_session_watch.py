from __future__ import annotations

from ulauncher.modes.launcher.session_watch import (
    ALL_WATCHES,
    LOGIN_WATCHES,
    OVERVIEW_WATCHES,
    SCREENSAVER_WATCHES,
    SessionWatcher,
    next_session_watch_action,
    properties_changed_should_close,
    screensaver_active_changed_should_close,
    session_signal_should_close,
)


def test_next_session_watch_action() -> None:
    assert next_session_watch_action(False, True) == "start"
    assert next_session_watch_action(True, False) == "stop"
    assert next_session_watch_action(True, True) == "keep"
    assert next_session_watch_action(False, False) == "keep"


def test_active_changed_closes_only_when_locked() -> None:
    assert screensaver_active_changed_should_close(True) is True
    assert screensaver_active_changed_should_close(False) is False
    assert session_signal_should_close("org.gnome.ScreenSaver", "ActiveChanged", (True,)) is True
    assert session_signal_should_close("org.gnome.ScreenSaver", "ActiveChanged", (False,)) is False
    assert session_signal_should_close("org.freedesktop.ScreenSaver", "ActiveChanged", [True]) is True
    assert session_signal_should_close("org.gnome.ScreenSaver", "Other", (True,)) is False
    assert len(SCREENSAVER_WATCHES) == 2


def test_overview_and_login_signals_close_the_popup() -> None:
    assert properties_changed_should_close("org.gnome.Shell", {"OverviewActive": True}) is True
    assert properties_changed_should_close("org.gnome.Shell", {"OverviewActive": False}) is False
    assert (
        session_signal_should_close(
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            ("org.gnome.Shell", {"OverviewActive": True}, []),
        )
        is True
    )
    assert (
        session_signal_should_close(
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            ("org.gnome.Shell", {"OverviewActive": False}, []),
        )
        is False
    )
    assert session_signal_should_close("org.freedesktop.login1.Session", "Lock", ()) is True
    assert session_signal_should_close("org.freedesktop.login1.Manager", "PrepareForSleep", (True,)) is True
    assert session_signal_should_close("org.freedesktop.login1.Manager", "PrepareForSleep", (False,)) is False
    assert properties_changed_should_close("org.freedesktop.login1.Session", {"LockedHint": True}) is True
    assert len(OVERVIEW_WATCHES) == 1
    assert len(LOGIN_WATCHES) == 3
    assert ALL_WATCHES[:2] == SCREENSAVER_WATCHES
    assert OVERVIEW_WATCHES[0] in ALL_WATCHES


def test_session_watcher_injected_subscribe_and_close() -> None:
    closed: list[str] = []
    subs: list[tuple[str, str, str, str]] = []

    def subscribe(dest: str, path: str, iface: str, member: str, _cb: object) -> int:
        subs.append((dest, path, iface, member))
        return len(subs)

    watcher = SessionWatcher(lambda: closed.append("close"), subscribe=subscribe)
    watcher.start()
    assert watcher.listening is True
    assert len(subs) == len(ALL_WATCHES)
    assert SCREENSAVER_WATCHES[0] in subs
    assert OVERVIEW_WATCHES[0] in subs
    watcher.start()
    assert len(subs) == len(ALL_WATCHES)
    watcher._on_signal("org.gnome.ScreenSaver", "ActiveChanged", (True,))
    assert closed == ["close"]
    watcher._on_signal("org.gnome.ScreenSaver", "ActiveChanged", (False,))
    assert closed == ["close"]
    watcher._on_signal(
        "org.freedesktop.DBus.Properties", "PropertiesChanged", ("org.gnome.Shell", {"OverviewActive": True}, [])
    )
    assert closed == ["close", "close"]
    watcher.stop()
    assert watcher.listening is False
    watcher.stop()
    assert closed == ["close", "close"]
