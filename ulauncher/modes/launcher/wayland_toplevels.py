"""List mapped toplevels via ext-foreign-toplevel-list-v1 (Mutter on GNOME Wayland).

org.gnome.Shell.Introspect.GetWindows is allowlisted to portal backends, so a
GTK app cannot use it. This protocol is what lswt speaks; we talk to the
compositor directly so window search works without that binary.
"""

from __future__ import annotations

import os
import socket
import struct
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

WL_DISPLAY_ID = 1
WL_DISPLAY_SYNC = 0
WL_DISPLAY_GET_REGISTRY = 1
WL_DISPLAY_ERROR = 0
WL_REGISTRY_BIND = 0
WL_REGISTRY_GLOBAL = 0
WL_CALLBACK_DONE = 0
EXT_LIST_IFACE = "ext_foreign_toplevel_list_v1"
EXT_LIST_TOPLEVEL = 0
EXT_LIST_FINISHED = 1
EXT_HANDLE_CLOSED = 0
EXT_HANDLE_DONE = 1
EXT_HANDLE_TITLE = 2
EXT_HANDLE_APP_ID = 3
EXT_HANDLE_IDENTIFIER = 4

CLIENT_ID_START = 2


def pack_wayland_message(object_id: int, opcode: int, payload: bytes = b"") -> bytes:
    size = 8 + len(payload)
    if size % 4:
        msg = "wayland message size must be 4-byte aligned"
        raise ValueError(msg)
    return struct.pack("<IHH", object_id, opcode, size) + payload


def pack_wayland_string(text: str) -> bytes:
    data = text.encode("utf-8") + b"\x00"
    pad = (4 - (len(data) % 4)) % 4
    return struct.pack("<I", len(data)) + data + (b"\x00" * pad)


def unpack_wayland_string(payload: bytes, offset: int = 0) -> tuple[str, int]:
    length = struct.unpack_from("<I", payload, offset)[0]
    start = offset + 4
    end = start + length
    if length < 1 or end > len(payload):
        msg = "wayland string overruns the message"
        raise ValueError(msg)
    text = payload[start : end - 1].decode("utf-8", "replace")
    padded = (length + 3) & ~3
    return text, offset + 4 + padded


def pop_wayland_message(buf: bytes) -> tuple[tuple[int, int, bytes] | None, bytes]:
    if len(buf) < 8:
        return None, buf
    object_id, opcode, size = struct.unpack_from("<IHH", buf, 0)
    if size < 8 or size % 4 or len(buf) < size:
        if size < 8 or size % 4:
            msg = "invalid wayland message header"
            raise ValueError(msg)
        return None, buf
    return (object_id, opcode, buf[8:size]), buf[size:]


def wayland_socket_path(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    display = env.get("WAYLAND_DISPLAY") or "wayland-0"
    if display.startswith("/"):
        return display
    runtime = env.get("XDG_RUNTIME_DIR") or ""
    if not runtime:
        return ""
    return os.path.join(runtime, display)


@dataclass
class _Handle:
    title: str = ""
    app_id: str = ""
    identifier: str = ""
    closed: bool = False
    done: bool = False


def collect_ext_foreign_handles(
    events: list[tuple[int, int, bytes]],
    list_id: int,
) -> list[dict[str, str]]:
    """Apply ext-foreign-toplevel-list events. Handle ids are compositor-allocated."""
    handles: dict[int, _Handle] = {}
    for object_id, opcode, payload in events:
        if object_id == list_id and opcode == EXT_LIST_TOPLEVEL:
            if len(payload) < 4:
                continue
            new_id = struct.unpack_from("<I", payload, 0)[0]
            handles[new_id] = _Handle()
            continue
        handle = handles.get(object_id)
        if handle is None or handle.closed:
            continue
        if opcode == EXT_HANDLE_CLOSED:
            handle.closed = True
        elif opcode == EXT_HANDLE_DONE:
            handle.done = True
        elif opcode == EXT_HANDLE_TITLE:
            handle.title, _ = unpack_wayland_string(payload)
        elif opcode == EXT_HANDLE_APP_ID:
            handle.app_id, _ = unpack_wayland_string(payload)
        elif opcode == EXT_HANDLE_IDENTIFIER:
            handle.identifier, _ = unpack_wayland_string(payload)
    rows: list[dict[str, str]] = []
    for handle in handles.values():
        if handle.closed or not handle.done or not handle.identifier:
            continue
        if not handle.title and not handle.app_id:
            continue
        rows.append({"identifier": handle.identifier, "title": handle.title, "app_id": handle.app_id})
    return rows


def _registry_globals(events: list[tuple[int, int, bytes]], registry_id: int) -> list[tuple[int, str, int]]:
    found: list[tuple[int, str, int]] = []
    for object_id, opcode, payload in events:
        if object_id != registry_id or opcode != WL_REGISTRY_GLOBAL:
            continue
        name = struct.unpack_from("<I", payload, 0)[0]
        iface, offset = unpack_wayland_string(payload, 4)
        version = struct.unpack_from("<I", payload, offset)[0]
        found.append((name, iface, version))
    return found


def _bind_ext_list(name: int, version: int, list_id: int) -> bytes:
    # wl_registry.bind new_id has no interface attribute, so the wire form is
    # name, interface string, version, object id.
    payload = struct.pack("<I", name) + pack_wayland_string(EXT_LIST_IFACE)
    payload += struct.pack("<II", min(version, 1), list_id)
    return pack_wayland_message(2, WL_REGISTRY_BIND, payload)


def _connect(environ: Mapping[str, str] | None) -> socket.socket | None:
    path = wayland_socket_path(environ)
    if not path:
        return None
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    try:
        sock.connect(path)
    except OSError:
        sock.close()
        return None
    return sock


def _recv_until_callback(sock: Any, callback_id: int, deadline: float) -> list[tuple[int, int, bytes]]:
    events: list[tuple[int, int, bytes]] = []
    buf = b""
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        while True:
            message, buf = pop_wayland_message(buf)
            if message is None:
                break
            object_id, opcode, _payload = message
            if object_id == WL_DISPLAY_ID and opcode == WL_DISPLAY_ERROR:
                msg = "wayland display error"
                raise OSError(msg)
            events.append(message)
            if object_id == callback_id and opcode == WL_CALLBACK_DONE:
                return events
    msg = "wayland roundtrip timed out"
    raise TimeoutError(msg)


def _run_list(sock: Any, timeout: float) -> list[dict[str, str]]:
    deadline = time.monotonic() + timeout
    registry_id = CLIENT_ID_START
    sync_id = CLIENT_ID_START + 1
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_GET_REGISTRY, struct.pack("<I", registry_id)))
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_SYNC, struct.pack("<I", sync_id)))
    intro = _recv_until_callback(sock, sync_id, deadline)
    list_name = 0
    list_version = 1
    for name, iface, version in _registry_globals(intro, registry_id):
        if iface == EXT_LIST_IFACE:
            list_name = name
            list_version = version
            break
    if not list_name:
        return []
    list_id = CLIENT_ID_START + 2
    done_id = CLIENT_ID_START + 3
    sock.sendall(_bind_ext_list(list_name, list_version, list_id))
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_SYNC, struct.pack("<I", done_id)))
    listed = _recv_until_callback(sock, done_id, deadline)
    return collect_ext_foreign_handles(listed, list_id)


def list_ext_foreign_toplevels(
    environ: Mapping[str, str] | None = None,
    timeout: float = 0.25,
    sock: Any = None,
) -> list[dict[str, str]]:
    """Return current toplevels, or [] when the protocol is missing or the socket fails."""
    owned = sock is None
    conn = sock if sock is not None else _connect(environ)
    if conn is None:
        return []
    try:
        return _run_list(conn, timeout)
    except (OSError, struct.error, ValueError, TimeoutError):
        return []
    finally:
        if owned:
            conn.close()


def ext_foreign_handle_to_window_fields(item: Mapping[str, Any]) -> dict[str, str] | None:
    ident = str(item.get("identifier") or "")
    title = str(item.get("title") or "")
    app_id = str(item.get("app_id") or item.get("app-id") or "")
    if not ident or (not title and not app_id):
        return None
    return {"identifier": ident, "title": title or app_id, "app_id": app_id}
