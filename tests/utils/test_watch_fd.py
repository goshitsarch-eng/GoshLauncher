"""watch_fd against a real GLib loop; test_scheduling.py mocks GLib away."""

from __future__ import annotations

import contextlib
import socket

from ulauncher.gi import GLib
from ulauncher.utils.scheduling import fd_is_hung_up, watch_fd


def _drain(sock: socket.socket) -> None:
    with contextlib.suppress(BlockingIOError, OSError):
        sock.recv(4096)


def test_watch_fd_stops_itself_when_the_peer_hangs_up() -> None:
    # A hung-up fd stays permanently ready, so a repeating source over one is re-dispatched as
    # fast as the loop can spin. A compositor restart used to pin a core for the whole session.
    ours, peer = socket.socketpair()
    ours.setblocking(False)
    calls: list[int] = []

    def on_readable() -> None:
        calls.append(1)
        _drain(ours)

    context = watch_fd(ours.fileno(), on_readable)
    peer.close()
    loop = GLib.MainLoop()
    GLib.timeout_add(150, lambda: (loop.quit(), False)[1])
    loop.run()
    context.cancel()
    ours.close()

    # one last dispatch so the watcher sees the EOF, then the source is gone
    assert calls == [1]
    assert context.source is None


def test_watch_fd_keeps_firing_while_the_peer_is_alive() -> None:
    ours, peer = socket.socketpair()
    ours.setblocking(False)
    calls: list[int] = []

    def on_readable() -> None:
        calls.append(1)
        _drain(ours)

    context = watch_fd(ours.fileno(), on_readable)
    loop = GLib.MainLoop()
    sent: list[int] = []

    def tick() -> bool:
        if len(sent) >= 4:
            loop.quit()
            return False
        sent.append(1)
        peer.send(b"x")
        return True

    GLib.timeout_add(20, tick)
    loop.run()
    still_watching = context.source is not None
    context.cancel()
    peer.close()
    ours.close()

    assert len(calls) >= 4
    assert still_watching


def test_fd_is_hung_up() -> None:
    ours, peer = socket.socketpair()
    ours.setblocking(False)
    assert fd_is_hung_up(ours.fileno()) is False
    peer.close()
    assert fd_is_hung_up(ours.fileno()) is True
    fd = ours.fileno()
    ours.close()
    # a closed fd counts as hung up rather than raising
    assert fd_is_hung_up(fd) is True
