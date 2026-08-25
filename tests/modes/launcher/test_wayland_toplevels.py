from __future__ import annotations

import struct

from ulauncher.modes.launcher.wayland_toplevels import (
    EXT_HANDLE_APP_ID,
    EXT_HANDLE_DONE,
    EXT_HANDLE_IDENTIFIER,
    EXT_HANDLE_TITLE,
    EXT_LIST_IFACE,
    EXT_LIST_TOPLEVEL,
    WL_CALLBACK_DONE,
    WL_REGISTRY_GLOBAL,
    collect_ext_foreign_handles,
    list_ext_foreign_toplevels,
    pack_wayland_message,
    pack_wayland_string,
    pop_wayland_message,
    unpack_wayland_string,
    wayland_socket_path,
)


def test_wayland_string_and_header_roundtrip() -> None:
    payload = pack_wayland_string("org.mozilla.firefox")
    text, offset = unpack_wayland_string(payload)
    assert text == "org.mozilla.firefox"
    assert offset == len(payload)
    message = pack_wayland_message(4, EXT_LIST_TOPLEVEL, struct.pack("<I", 0xFF000001))
    parsed, rest = pop_wayland_message(message)
    assert rest == b""
    assert parsed is not None
    object_id, opcode, body = parsed
    assert object_id == 4
    assert opcode == EXT_LIST_TOPLEVEL
    assert struct.unpack_from("<I", body, 0)[0] == 0xFF000001
    incomplete, leftover = pop_wayland_message(message[:6])
    assert incomplete is None
    assert leftover == message[:6]


def test_collect_ext_foreign_handles_skips_closed_and_incomplete() -> None:
    list_id = 4
    handle = 0xFF000001
    closed = 0xFF000002
    events = [
        (list_id, EXT_LIST_TOPLEVEL, struct.pack("<I", handle)),
        (handle, EXT_HANDLE_TITLE, pack_wayland_string("Mozilla Firefox")),
        (handle, EXT_HANDLE_APP_ID, pack_wayland_string("org.mozilla.firefox")),
        (handle, EXT_HANDLE_IDENTIFIER, pack_wayland_string("gen-1")),
        (handle, EXT_HANDLE_DONE, b""),
        (list_id, EXT_LIST_TOPLEVEL, struct.pack("<I", closed)),
        (closed, EXT_HANDLE_TITLE, pack_wayland_string("Panel")),
        (closed, EXT_HANDLE_APP_ID, pack_wayland_string("gnome-shell")),
        (closed, EXT_HANDLE_IDENTIFIER, pack_wayland_string("gen-panel")),
        (closed, EXT_HANDLE_DONE, b""),
        (closed, 0, b""),
    ]
    rows = collect_ext_foreign_handles(events, list_id)
    assert rows == [{"identifier": "gen-1", "title": "Mozilla Firefox", "app_id": "org.mozilla.firefox"}]


def test_wayland_socket_path_uses_runtime_dir() -> None:
    assert wayland_socket_path({"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000"}) == (
        "/run/user/1000/wayland-1"
    )
    assert wayland_socket_path({"WAYLAND_DISPLAY": "/tmp/custom", "XDG_RUNTIME_DIR": "/run/user/1000"}) == "/tmp/custom"
    assert wayland_socket_path({"WAYLAND_DISPLAY": "wayland-0"}) == ""


class _ScriptedDisplay:
    def __init__(self) -> None:
        self._phase = 0
        self._out = b""

    def sendall(self, _data: bytes) -> None:
        self._phase += 1
        if self._phase == 2:
            global_payload = struct.pack("<I", 7) + pack_wayland_string(EXT_LIST_IFACE) + struct.pack("<I", 1)
            self._out += pack_wayland_message(2, WL_REGISTRY_GLOBAL, global_payload)
            self._out += pack_wayland_message(3, WL_CALLBACK_DONE, struct.pack("<I", 0))
        elif self._phase == 4:
            handle = 0xFF000010
            self._out += pack_wayland_message(4, EXT_LIST_TOPLEVEL, struct.pack("<I", handle))
            self._out += pack_wayland_message(handle, EXT_HANDLE_TITLE, pack_wayland_string("Settings"))
            self._out += pack_wayland_message(handle, EXT_HANDLE_APP_ID, pack_wayland_string("org.gnome.Settings"))
            self._out += pack_wayland_message(handle, EXT_HANDLE_IDENTIFIER, pack_wayland_string("gen-settings"))
            self._out += pack_wayland_message(handle, EXT_HANDLE_DONE, b"")
            self._out += pack_wayland_message(5, WL_CALLBACK_DONE, struct.pack("<I", 1))

    def recv(self, _size: int) -> bytes:
        data = self._out
        self._out = b""
        return data

    def close(self) -> None:
        return None


def test_list_ext_foreign_toplevels_from_scripted_display() -> None:
    rows = list_ext_foreign_toplevels(sock=_ScriptedDisplay(), timeout=1.0)
    assert rows == [{"identifier": "gen-settings", "title": "Settings", "app_id": "org.gnome.Settings"}]


def test_list_ext_foreign_toplevels_missing_socket_is_empty() -> None:
    assert list_ext_foreign_toplevels(environ={"WAYLAND_DISPLAY": "missing", "XDG_RUNTIME_DIR": "/tmp"}) == []
