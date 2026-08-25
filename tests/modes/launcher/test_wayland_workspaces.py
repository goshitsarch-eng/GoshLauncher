from __future__ import annotations

import struct

from ulauncher.modes.launcher.wayland_toplevels import (
    WL_CALLBACK_DONE,
    WL_REGISTRY_GLOBAL,
    pack_wayland_message,
    pack_wayland_string,
    pack_wayland_uint32_array,
    pop_wayland_message,
    unpack_wayland_uint32_array,
)
from ulauncher.modes.launcher.wayland_workspaces import (
    EXT_WS_ACTIVATE,
    EXT_WS_CAPABILITIES,
    EXT_WS_COORDINATES,
    EXT_WS_MANAGER_COMMIT,
    EXT_WS_MANAGER_DONE,
    EXT_WS_MANAGER_IFACE,
    EXT_WS_MANAGER_WORKSPACE,
    EXT_WS_NAME,
    EXT_WS_REMOVED,
    activate_ext_workspace,
    collect_ext_workspace_handles,
    list_ext_workspaces,
    pick_ext_workspace,
)


def test_wayland_uint32_array_roundtrip() -> None:
    payload = pack_wayland_uint32_array([1])
    values, offset = unpack_wayland_uint32_array(payload)
    assert values == [1]
    assert offset == len(payload)
    empty, empty_off = unpack_wayland_uint32_array(pack_wayland_uint32_array([]))
    assert empty == []
    assert empty_off == 4


def test_collect_ext_workspace_handles_skips_removed() -> None:
    manager_id = 4
    first = 0xFF000001
    removed = 0xFF000002
    events = [
        (manager_id, EXT_WS_MANAGER_WORKSPACE, struct.pack("<I", first)),
        (first, EXT_WS_NAME, pack_wayland_string("1")),
        (first, EXT_WS_COORDINATES, pack_wayland_uint32_array([0])),
        (first, EXT_WS_CAPABILITIES, struct.pack("<I", 1)),
        (manager_id, EXT_WS_MANAGER_WORKSPACE, struct.pack("<I", removed)),
        (removed, EXT_WS_NAME, pack_wayland_string("2")),
        (removed, EXT_WS_COORDINATES, pack_wayland_uint32_array([1])),
        (removed, EXT_WS_REMOVED, b""),
        (manager_id, EXT_WS_MANAGER_DONE, b""),
    ]
    rows = collect_ext_workspace_handles(events, manager_id)
    assert [row["object_id"] for row in rows] == [first, removed]
    assert rows[1]["removed"] is True
    assert pick_ext_workspace(rows, 1) is None
    picked = pick_ext_workspace(rows, 0)
    assert picked is not None
    assert picked["object_id"] == first


def test_pick_ext_workspace_coords_name_and_order() -> None:
    rows = [
        {"object_id": 1, "name": "other", "coordinates": [5], "removed": False},
        {"object_id": 2, "name": "2", "coordinates": [], "removed": False},
        {"object_id": 3, "name": "", "coordinates": [0], "removed": False},
    ]
    by_coord = pick_ext_workspace(rows, 0)
    assert by_coord is not None
    assert by_coord["object_id"] == 3
    by_name = pick_ext_workspace(rows, 1)
    assert by_name is not None
    assert by_name["object_id"] == 2
    named = [
        {"object_id": 8, "name": "Workspace 3", "coordinates": [], "removed": False},
        {"object_id": 9, "name": "skip", "coordinates": [], "removed": False},
    ]
    by_label = pick_ext_workspace(named, 2)
    assert by_label is not None
    assert by_label["object_id"] == 8
    ordered = [
        {"object_id": 4, "name": "", "coordinates": [], "removed": False},
        {"object_id": 5, "name": "", "coordinates": [], "removed": False},
    ]
    by_order = pick_ext_workspace(ordered, 1)
    assert by_order is not None
    assert by_order["object_id"] == 5
    assert pick_ext_workspace(ordered, 9) is None


class _ScriptedWorkspaceDisplay:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self._phase = 0
        self._out = b""

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)
        self._phase += 1
        if self._phase == 2:
            global_payload = struct.pack("<I", 9) + pack_wayland_string(EXT_WS_MANAGER_IFACE) + struct.pack("<I", 1)
            self._out += pack_wayland_message(2, WL_REGISTRY_GLOBAL, global_payload)
            self._out += pack_wayland_message(3, WL_CALLBACK_DONE, struct.pack("<I", 0))
        elif self._phase == 4:
            first = 0xFF000001
            second = 0xFF000002
            self._out += pack_wayland_message(4, EXT_WS_MANAGER_WORKSPACE, struct.pack("<I", first))
            self._out += pack_wayland_message(first, EXT_WS_NAME, pack_wayland_string("1"))
            self._out += pack_wayland_message(first, EXT_WS_COORDINATES, pack_wayland_uint32_array([0]))
            self._out += pack_wayland_message(first, EXT_WS_CAPABILITIES, struct.pack("<I", 1))
            self._out += pack_wayland_message(4, EXT_WS_MANAGER_WORKSPACE, struct.pack("<I", second))
            self._out += pack_wayland_message(second, EXT_WS_NAME, pack_wayland_string("2"))
            self._out += pack_wayland_message(second, EXT_WS_COORDINATES, pack_wayland_uint32_array([1]))
            self._out += pack_wayland_message(second, EXT_WS_CAPABILITIES, struct.pack("<I", 1))
            self._out += pack_wayland_message(4, EXT_WS_MANAGER_DONE, b"")
            self._out += pack_wayland_message(5, WL_CALLBACK_DONE, struct.pack("<I", 1))
        elif self._phase == 5:
            self._out += pack_wayland_message(6, WL_CALLBACK_DONE, struct.pack("<I", 2))

    def recv(self, _size: int) -> bytes:
        data = self._out
        self._out = b""
        return data

    def close(self) -> None:
        return None


def _messages(buf: bytes) -> list[tuple[int, int, bytes]]:
    found: list[tuple[int, int, bytes]] = []
    rest = buf
    while rest:
        message, rest = pop_wayland_message(rest)
        if message is None:
            break
        found.append(message)
    return found


def test_list_ext_workspaces_from_scripted_display() -> None:
    rows = list_ext_workspaces(sock=_ScriptedWorkspaceDisplay(), timeout=1.0)
    assert rows is not None
    assert [row["name"] for row in rows] == ["1", "2"]


def test_activate_ext_workspace_from_scripted_display() -> None:
    display = _ScriptedWorkspaceDisplay()
    assert activate_ext_workspace(1, sock=display, timeout=1.0) is True
    burst = _messages(display.sent[-1])
    assert burst[0][:2] == (0xFF000002, EXT_WS_ACTIVATE)
    assert burst[1][:2] == (4, EXT_WS_MANAGER_COMMIT)


def test_activate_ext_workspace_missing_protocol_or_socket() -> None:
    class _NoManager:
        def __init__(self) -> None:
            self._phase = 0
            self._out = b""

        def sendall(self, _data: bytes) -> None:
            self._phase += 1
            if self._phase == 2:
                self._out += pack_wayland_message(3, WL_CALLBACK_DONE, struct.pack("<I", 0))

        def recv(self, _size: int) -> bytes:
            data = self._out
            self._out = b""
            return data

        def close(self) -> None:
            return None

    assert activate_ext_workspace(0, sock=_NoManager(), timeout=1.0) is False
    assert list_ext_workspaces(sock=_NoManager(), timeout=1.0) is None
    assert activate_ext_workspace(0, environ={"WAYLAND_DISPLAY": "missing", "XDG_RUNTIME_DIR": "/tmp"}) is False
    assert list_ext_workspaces(environ={"WAYLAND_DISPLAY": "missing", "XDG_RUNTIME_DIR": "/tmp"}) is None
