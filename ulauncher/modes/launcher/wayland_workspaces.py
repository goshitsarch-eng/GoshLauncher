"""Activate a workspace via ext-workspace-v1 (Mutter on GNOME Wayland).

GNOME Wayland has no EWMH desktop, and Shell.Eval / Introspect cannot switch
workspaces from a GTK app. This protocol is the compositor stand-in for
MetaWorkspace.activate. After activate the client must commit on the manager.
Missing globals are a no-op so older Mutter can fall through to wmctrl/EWMH.
"""

from __future__ import annotations

import struct
import time
from collections.abc import Mapping, Sequence
from typing import Any

from ulauncher.modes.launcher.wayland_toplevels import (
    CLIENT_ID_START,
    WL_DISPLAY_GET_REGISTRY,
    WL_DISPLAY_ID,
    WL_DISPLAY_SYNC,
    WL_REGISTRY_BIND,
    _connect,
    _recv_until_callback,
    _registry_globals,
    pack_wayland_message,
    pack_wayland_string,
    unpack_wayland_string,
    unpack_wayland_uint32_array,
)

EXT_WS_MANAGER_IFACE = "ext_workspace_manager_v1"
EXT_WS_MANAGER_COMMIT = 0
EXT_WS_MANAGER_WORKSPACE = 1
EXT_WS_MANAGER_DONE = 2
EXT_WS_ID = 0
EXT_WS_NAME = 1
EXT_WS_COORDINATES = 2
EXT_WS_STATE = 3
EXT_WS_CAPABILITIES = 4
EXT_WS_REMOVED = 5
EXT_WS_ACTIVATE = 1
WS_CAP_ACTIVATE = 1


def collect_ext_workspace_handles(
    events: list[tuple[int, int, bytes]],
    manager_id: int,
) -> list[dict[str, Any]]:
    """Apply ext-workspace-manager events. Handle ids are compositor-allocated."""
    handles: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for object_id, opcode, payload in events:
        if object_id == manager_id and opcode == EXT_WS_MANAGER_WORKSPACE:
            if len(payload) < 4:
                continue
            new_id = struct.unpack_from("<I", payload, 0)[0]
            handles[new_id] = {
                "object_id": new_id,
                "id": "",
                "name": "",
                "coordinates": [],
                "state": 0,
                "capabilities": WS_CAP_ACTIVATE,
                "removed": False,
            }
            order.append(new_id)
            continue
        handle = handles.get(object_id)
        if handle is None:
            continue
        if opcode == EXT_WS_REMOVED:
            handle["removed"] = True
        elif opcode == EXT_WS_ID:
            handle["id"], _ = unpack_wayland_string(payload)
        elif opcode == EXT_WS_NAME:
            handle["name"], _ = unpack_wayland_string(payload)
        elif opcode == EXT_WS_COORDINATES:
            handle["coordinates"], _ = unpack_wayland_uint32_array(payload)
        elif opcode == EXT_WS_STATE and len(payload) >= 4:
            handle["state"] = struct.unpack_from("<I", payload, 0)[0]
        elif opcode == EXT_WS_CAPABILITIES and len(payload) >= 4:
            handle["capabilities"] = struct.unpack_from("<I", payload, 0)[0]
    return [handles[item_id] for item_id in order]


def pick_ext_workspace(items: Sequence[Mapping[str, Any]], index: int) -> dict[str, Any] | None:
    """Match goshos get_workspace_by_index: 1D coords, then name, then creation order."""
    live = [dict(item) for item in items if not item.get("removed")]
    number = index + 1
    for item in live:
        coords = item.get("coordinates") or []
        if isinstance(coords, (list, tuple)) and len(coords) == 1 and int(coords[0]) == index:
            return item
    wanted = {str(number), f"workspace {number}"}
    for item in live:
        name = str(item.get("name") or "").strip().lower()
        if name in wanted:
            return item
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(live):
        return live[index]
    return None


def _bind_ext_workspace_manager(name: int, version: int, manager_id: int) -> bytes:
    payload = struct.pack("<I", name) + pack_wayland_string(EXT_WS_MANAGER_IFACE)
    payload += struct.pack("<II", min(version, 1), manager_id)
    return pack_wayland_message(CLIENT_ID_START, WL_REGISTRY_BIND, payload)


def _find_manager(events: list[tuple[int, int, bytes]], registry_id: int) -> tuple[int, int]:
    for name, iface, version in _registry_globals(events, registry_id):
        if iface == EXT_WS_MANAGER_IFACE:
            return name, version
    return 0, 1


def _run_activate(sock: Any, index: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    registry_id = CLIENT_ID_START
    sync_id = CLIENT_ID_START + 1
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_GET_REGISTRY, struct.pack("<I", registry_id)))
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_SYNC, struct.pack("<I", sync_id)))
    intro = _recv_until_callback(sock, sync_id, deadline)
    mgr_name, mgr_version = _find_manager(intro, registry_id)
    if not mgr_name:
        return False
    manager_id = CLIENT_ID_START + 2
    done_id = CLIENT_ID_START + 3
    sock.sendall(_bind_ext_workspace_manager(mgr_name, mgr_version, manager_id))
    sock.sendall(pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_SYNC, struct.pack("<I", done_id)))
    listed = _recv_until_callback(sock, done_id, deadline)
    picked = pick_ext_workspace(collect_ext_workspace_handles(listed, manager_id), index)
    if picked is None:
        return False
    ack_id = CLIENT_ID_START + 4
    sock.sendall(
        pack_wayland_message(int(picked["object_id"]), EXT_WS_ACTIVATE)
        + pack_wayland_message(manager_id, EXT_WS_MANAGER_COMMIT)
        + pack_wayland_message(WL_DISPLAY_ID, WL_DISPLAY_SYNC, struct.pack("<I", ack_id))
    )
    try:
        _recv_until_callback(sock, ack_id, deadline)
    except TimeoutError:
        return True
    return True


def activate_ext_workspace(
    index: int,
    environ: Mapping[str, str] | None = None,
    timeout: float = 0.4,
    sock: Any = None,
) -> bool:
    """Activate the workspace at 0-based index. False when the protocol is missing."""
    owned = sock is None
    conn = sock if sock is not None else _connect(environ)
    if conn is None:
        return False
    try:
        return _run_activate(conn, index, timeout)
    except (OSError, struct.error, ValueError, TimeoutError):
        return False
    finally:
        if owned:
            conn.close()
