from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.x11_live import (
    X11_LIVE_ATOMS,
    X11_PROPERTY_NOTIFY,
    drain_x11_live_events,
    intern_x11_live_atoms,
    is_x11_live_atom,
    x11_display_fileno,
)


def test_x11_live_atoms_cover_goshos_window_and_workspace_signals() -> None:
    assert is_x11_live_atom("_NET_CURRENT_DESKTOP")
    assert is_x11_live_atom("_NET_NUMBER_OF_DESKTOPS")
    assert is_x11_live_atom("_NET_ACTIVE_WINDOW")
    assert is_x11_live_atom("_NET_CLIENT_LIST")
    assert is_x11_live_atom("_NET_CLIENT_LIST_STACKING")
    assert not is_x11_live_atom("_NET_WM_NAME")
    assert len(X11_LIVE_ATOMS) == 5


def test_intern_x11_live_atoms_maps_ids() -> None:
    names = iter(range(10, 20))

    class Display:
        def intern_atom(self, _name: str) -> int:
            return next(names)

    interned = intern_x11_live_atoms(Display())
    assert interned[10] == "_NET_CURRENT_DESKTOP"
    assert interned[14] == "_NET_CLIENT_LIST_STACKING"


def test_x11_display_fileno_uses_socket_when_display_has_no_fileno() -> None:
    display = SimpleNamespace(display=SimpleNamespace(socket=SimpleNamespace(fileno=lambda: 11)))
    assert x11_display_fileno(display) == 11
    assert x11_display_fileno(SimpleNamespace(fileno=lambda: 4)) == 4


def test_drain_x11_live_events_notifies_only_for_live_atoms() -> None:
    live = {7: "_NET_CURRENT_DESKTOP"}
    queue = [
        SimpleNamespace(type=X11_PROPERTY_NOTIFY, atom=7),
        SimpleNamespace(type=X11_PROPERTY_NOTIFY, atom=99),
        SimpleNamespace(type=2, atom=7),
    ]

    class Display:
        def pending_events(self) -> int:
            return len(queue)

        def next_event(self) -> SimpleNamespace:
            return queue.pop(0)

    assert drain_x11_live_events(Display(), live) is True
    assert queue == []


def test_drain_x11_live_events_ignores_unrelated_properties() -> None:
    queue = [SimpleNamespace(type=X11_PROPERTY_NOTIFY, atom=3)]

    class Display:
        def pending_events(self) -> int:
            return len(queue)

        def next_event(self) -> SimpleNamespace:
            return queue.pop(0)

    assert drain_x11_live_events(Display(), {1: "_NET_ACTIVE_WINDOW"}) is False
