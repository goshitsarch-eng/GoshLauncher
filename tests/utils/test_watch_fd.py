"""watch_fd against the real MiniLoop backend; test_scheduling.py covers the API surface."""

from __future__ import annotations

import contextlib
import socket

from tests.utils.loop_helpers import process_pending_events
from ulauncher.utils.scheduling import fd_is_hung_up, watch_fd


def _drain(sock: socket.socket) -> None:
    with contextlib.suppress(BlockingIOError, OSError):
        sock.recv(4096)


def test_watch_fd_stops_itself_when_the_peer_hangs_up() -> None:
    # A hung-up fd stays permanently ready, so a repeating watch over one is re-dispatched as
    # fast as the loop can spin. A compositor restart used to pin a core for the whole session.
    ours, peer = socket.socketpair()
    ours.setblocking(False)
    calls: list[int] = []

    def on_readable() -> None:
        calls.append(1)
        _drain(ours)

    context = watch_fd(ours.fileno(), on_readable)
    peer.close()
    process_pending_events(0.15)
    context.cancel()
    ours.close()

    # one last dispatch so the watcher sees the EOF, then the watch is gone
    assert calls == [1]
    assert not context.active


def test_watch_fd_keeps_firing_while_the_peer_is_alive() -> None:
    ours, peer = socket.socketpair()
    ours.setblocking(False)
    calls: list[int] = []

    def on_readable() -> None:
        calls.append(1)
        _drain(ours)

    context = watch_fd(ours.fileno(), on_readable)
    peer.sendall(b"a")
    process_pending_events(0.05)
    peer.sendall(b"b")
    process_pending_events(0.05)
    assert len(calls) >= 2
    assert context.active

    context.cancel()
    peer.close()
    ours.close()


def test_fd_is_hung_up() -> None:
    ours, peer = socket.socketpair()
    assert not fd_is_hung_up(ours.fileno())
    peer.close()
    assert fd_is_hung_up(ours.fileno())
    fd = ours.fileno()
    ours.close()
    assert fd_is_hung_up(fd)
