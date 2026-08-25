"""AT-SPI stand-in for Mutter get_tab_list recency, raise, win.delete, and pid.

ext-foreign-toplevel-list has no activate/close/pid, and Introspect GetWindows is
allowlisted to portal backends. When the session a11y bus is already enabled,
Window:Activate is the public focus order, Component.GrabFocus is the
per-window raise, Action.DoAction("close") is win.delete for non-GTK
surfaces, and GetConnectionUnixProcessID on that bus is win.kill's pid.
This module never writes org.a11y.Status.IsEnabled.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ulauncher.modes.launcher.windows import WindowInfo

logger = logging.getLogger(__name__)

ATSPI_LISTED_ROLES = frozenset({"frame", "window", "dialog", "alert", "file chooser"})
ATSPI_SKIP_ROLES = frozenset(
    {
        "panel",
        "tool bar",
        "toolbar",
        "tooltip",
        "notification",
        "status bar",
        "menu bar",
        "popup menu",
        "desktop frame",
    }
)
ATSPI_ROOT_NAME = "org.a11y.atspi.Registry"
ATSPI_ROOT_PATH = "/org/a11y/atspi/accessible/root"
ATSPI_ACCESSIBLE = "org.a11y.atspi.Accessible"
ATSPI_ACTION = "org.a11y.atspi.Action"
ATSPI_COMPONENT = "org.a11y.atspi.Component"
ATSPI_WINDOW_EVENT = "org.a11y.atspi.Event.Window"
ATSPI_CLOSE_ACTION_NAMES = frozenset({"close", "gtk-close", "win.close"})
ATSPI_BUTTON_ROLES = frozenset({"push button", "button"})
ATSPI_WALK_ROLES = frozenset(
    {
        "frame",
        "window",
        "dialog",
        "alert",
        "file chooser",
        "filler",
        "panel",
        "layered pane",
        "title bar",
        "tool bar",
        "toolbar",
        "root pane",
        "glass pane",
        "internal frame",
    }
)
_FOCUS_HISTORY_MAX = 32
_CLOSE_WALK_MAX = 8
_CLOSE_WALK_DEPTH = 2

_FOCUS_HISTORY: list[str] = []


def atspi_role_is_listed(role_name: str) -> bool:
    return str(role_name or "").strip().lower() in ATSPI_LISTED_ROLES


def atspi_role_is_skip_taskbar(role_name: str) -> bool:
    return str(role_name or "").strip().lower() in ATSPI_SKIP_ROLES


def atspi_window_type(role_name: str) -> str:
    role = str(role_name or "").strip().lower()
    if role in {"dialog", "alert", "file chooser"}:
        return "dialog"
    if atspi_role_is_skip_taskbar(role):
        return "dock"
    return "normal"


def atspi_ref(bus_name: str, object_path: str) -> str:
    if not bus_name or not object_path:
        return ""
    return f"{bus_name}\0{object_path}"


def split_atspi_ref(ref: str) -> tuple[str, str] | None:
    bus_name, sep, object_path = str(ref or "").partition("\0")
    if not sep or not bus_name or not object_path:
        return None
    return bus_name, object_path


def note_atspi_focus(title: str, app_id: str = "") -> None:
    """Record a Window:Activate so search can sort like get_tab_list."""
    keys = [key for key in ((app_id or "").strip().lower(), (title or "").strip().lower()) if key]
    for key in keys:
        while key in _FOCUS_HISTORY:
            _FOCUS_HISTORY.remove(key)
        _FOCUS_HISTORY.insert(0, key)
    del _FOCUS_HISTORY[_FOCUS_HISTORY_MAX:]


def reset_atspi_focus_history() -> None:
    _FOCUS_HISTORY.clear()


def atspi_focus_ranks(history: Sequence[str] | None = None) -> dict[str, int]:
    rows = list(_FOCUS_HISTORY if history is None else history)
    return {key: index for index, key in enumerate(rows)}


def windows_from_atspi_nodes(nodes: Any) -> list[WindowInfo]:
    """Map AT-SPI window dicts onto WindowInfo. Keep skip-taskbar chrome for IME."""
    from ulauncher.modes.launcher.windows import WindowInfo as Win

    if not isinstance(nodes, list):
        return []
    windows: list[Win] = []
    for item in nodes:
        if not isinstance(item, dict):
            continue
        win = _window_from_atspi_node(item)
        if win is not None:
            windows.append(win)
    return windows


def close_action_index(names: Sequence[str]) -> int | None:
    for index, name in enumerate(names):
        if str(name or "").strip().lower() in ATSPI_CLOSE_ACTION_NAMES:
            return index
    return None


def is_atspi_close_button(role_name: str, accessible_name: str) -> bool:
    role = str(role_name or "").strip().lower()
    if role not in ATSPI_BUTTON_ROLES:
        return False
    label = str(accessible_name or "").strip().lower()
    return label in ATSPI_CLOSE_ACTION_NAMES or label.startswith("close")


def pick_close_action(role_name: str, accessible_name: str, actions: Sequence[str]) -> int | None:
    index = close_action_index(actions)
    if index is not None:
        return index
    if is_atspi_close_button(role_name, accessible_name) and actions:
        return 0
    return None


def grab_atspi_focus(
    ref: str,
    title: str = "",
    app_id: str = "",
    *,
    grab: Callable[[str], bool] | None = None,
    find_ref: Callable[[str, str], str] | None = None,
) -> bool:
    """Raise one window. Prefer a stored ref; otherwise match title/app_id."""
    grab_fn = grab or _grab_ref
    target = str(ref or "")
    if not target and (title or app_id):
        finder = find_ref or _find_ref_for_title
        target = finder(title, app_id)
    if not target:
        return False
    return bool(grab_fn(target))


def atspi_close(
    ref: str,
    title: str = "",
    app_id: str = "",
    *,
    close_ref: Callable[[str], bool] | None = None,
    find_ref: Callable[[str, str], str] | None = None,
) -> bool:
    """Ask one window to close. goshos win.delete; ext-foreign has no request."""
    close_fn = close_ref or _close_ref
    target = str(ref or "")
    if not target and (title or app_id):
        finder = find_ref or _find_ref_for_title
        target = finder(title, app_id)
    if not target:
        return False
    return bool(close_fn(target))


def list_atspi_windows(probe: Callable[[], list[WindowInfo]] | None = None) -> list[WindowInfo]:
    """Best-effort a11y snapshot. Empty when the session has a11y off."""
    if probe is not None:
        return list(probe())
    try:
        return _list_atspi_windows()
    except Exception:
        logger.debug("AT-SPI window list failed", exc_info=True)
        return []


class AtspiLiveWatch:
    """Subscribe to Window Create/Destroy/Activate on the a11y bus.

    goshos uses display window-created, unmanaged, and get_tab_list. Those
    Mutter signals are not exported to GTK apps; AT-SPI Window events are.
    """

    def __init__(self) -> None:
        self._conn: Any = None
        self._ids: list[int] = []
        self._on_change: Callable[[], None] | None = None

    def start(self, on_change: Callable[[], None], connection: Any | None = None) -> bool:
        if self._conn is not None:
            return True
        conn = connection if connection is not None else _a11y_connection()
        if conn is None:
            return False
        self._on_change = on_change
        self._conn = conn
        self._ids = []
        for member in ("Activate", "Create", "Destroy"):
            watch_id = _subscribe_window_event(conn, member, self._on_event)
            if watch_id:
                self._ids.append(int(watch_id))
        if self._ids:
            return True
        self.stop()
        return False

    def stop(self) -> None:
        conn = self._conn
        if conn is not None:
            for watch_id in self._ids:
                with contextlib.suppress(AttributeError, RuntimeError, TypeError, OSError):
                    conn.signal_unsubscribe(watch_id)
        self._conn = None
        self._ids = []
        self._on_change = None

    def _on_event(self, *args: Any) -> None:
        member = str(args[3] or "") if len(args) >= 4 else ""
        dest = str(args[0] or "") if args else ""
        path = str(args[2] or "") if len(args) >= 3 else ""
        if member == "Activate" and dest and path:
            title, app_id = _accessible_title_and_app(self._conn, dest, path)
            note_atspi_focus(title, app_id)
        on_change = self._on_change
        if on_change is not None:
            on_change()


def _window_from_atspi_node(item: Mapping[str, Any]) -> WindowInfo | None:
    from ulauncher.modes.launcher.windows import WindowInfo as Win

    role = str(item.get("role") or item.get("role_name") or "")
    title = str(item.get("title") or item.get("name") or "")
    app_id = str(item.get("app_id") or item.get("app-id") or "")
    bus_name = str(item.get("bus_name") or item.get("name_owner") or "")
    object_path = str(item.get("path") or item.get("object_path") or "")
    if not title and not app_id:
        return None
    if not atspi_role_is_listed(role) and not atspi_role_is_skip_taskbar(role):
        return None
    ident = object_path or title
    try:
        pid = int(item.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    return Win(
        wid=f"atspi:{ident}",
        title=title or app_id,
        wm_class=app_id,
        desktop=0,
        pid=pid,
        app_id=app_id,
        user_time=1 if item.get("active") or item.get("has-focus") else 0,
        skip_taskbar=atspi_role_is_skip_taskbar(role),
        window_type=atspi_window_type(role),
        atspi_ref=atspi_ref(bus_name, object_path),
    )


def _dbus_call(
    conn: Any,
    dest: str,
    path: str,
    iface: str,
    method: str,
    signature: str,
    params: Any = None,
) -> Any:
    from ulauncher.gi import Gio, GLib

    reply = conn.call_sync(
        dest,
        path,
        iface,
        method,
        params,
        GLib.VariantType.new(signature),
        Gio.DBusCallFlags.NONE,
        50,
        None,
    )
    return reply.unpack()[0]


def _a11y_enabled(session: Any) -> bool:
    try:
        from ulauncher.gi import GLib

        value = _dbus_call(
            session,
            "org.a11y.Bus",
            "/org/a11y/bus",
            "org.freedesktop.DBus.Properties",
            "Get",
            "(v)",
            GLib.Variant("(ss)", ("org.a11y.Status", "IsEnabled")),
        )
    except Exception:
        return False
    return bool(value)


def _a11y_connection() -> Any | None:
    try:
        from ulauncher.gi import Gio
    except (ImportError, AttributeError, RuntimeError, OSError):
        return None
    try:
        session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if not _a11y_enabled(session):
            return None
        address = str(_dbus_call(session, "org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus", "GetAddress", "(s)") or "")
        if not address:
            return None
        flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        return Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
    except Exception:
        logger.debug("AT-SPI bus connection failed", exc_info=True)
        return None


def _subscribe_window_event(conn: Any, member: str, callback: Callable[..., None]) -> int:
    try:
        from ulauncher.gi import Gio

        watch_id = conn.signal_subscribe(
            None,
            ATSPI_WINDOW_EVENT,
            member,
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            callback,
        )
    except (AttributeError, TypeError, RuntimeError, OSError, ValueError):
        return 0
    return int(watch_id or 0)


def _accessible_name(conn: Any, dest: str, path: str) -> str:
    try:
        from ulauncher.gi import GLib

        value = _dbus_call(
            conn,
            dest,
            path,
            "org.freedesktop.DBus.Properties",
            "Get",
            "(v)",
            GLib.Variant("(ss)", (ATSPI_ACCESSIBLE, "Name")),
        )
    except Exception:
        return ""
    return str(value or "")


def _accessible_title_and_app(conn: Any, dest: str, path: str) -> tuple[str, str]:
    title = _accessible_name(conn, dest, path)
    app_id = dest
    try:
        app = _dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetApplication", "(so)")
        if isinstance(app, tuple) and app:
            app_id = str(app[0] or dest)
    except Exception:
        logger.debug("AT-SPI GetApplication failed", exc_info=True)
    return title, app_id


def _grab_ref(ref: str) -> bool:
    parts = split_atspi_ref(ref)
    if parts is None:
        return False
    bus_name, object_path = parts
    conn = _a11y_connection()
    if conn is None:
        return False
    try:
        return bool(_dbus_call(conn, bus_name, object_path, ATSPI_COMPONENT, "GrabFocus", "(b)"))
    except Exception:
        logger.debug("AT-SPI GrabFocus failed", exc_info=True)
        return False


def _close_ref(ref: str) -> bool:
    parts = split_atspi_ref(ref)
    if parts is None:
        return False
    bus_name, object_path = parts
    conn = _a11y_connection()
    if conn is None:
        return False
    return _close_accessible(conn, bus_name, object_path, 0, set(), [_CLOSE_WALK_MAX])


def _should_walk_atspi_role(role_name: str, *, root: bool = False) -> bool:
    if root:
        return True
    return str(role_name or "").strip().lower() in ATSPI_WALK_ROLES


def _accessible_role(conn: Any, dest: str, path: str) -> str:
    try:
        return str(_dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetRoleName", "(s)") or "")
    except Exception:
        return ""


def _action_names(conn: Any, dest: str, path: str) -> list[str]:
    from ulauncher.gi import GLib

    try:
        rows = _dbus_call(conn, dest, path, ATSPI_ACTION, "GetActions", "(a(sss))")
        if isinstance(rows, (list, tuple)):
            return [str(row[0]) for row in rows if isinstance(row, (list, tuple)) and row]
    except Exception:
        logger.debug("AT-SPI GetActions failed", exc_info=True)
    try:
        count = int(
            _dbus_call(
                conn,
                dest,
                path,
                "org.freedesktop.DBus.Properties",
                "Get",
                "(v)",
                GLib.Variant("(ss)", (ATSPI_ACTION, "NActions")),
            )
            or 0
        )
    except Exception:
        return []
    names: list[str] = []
    for index in range(min(max(count, 0), 16)):
        try:
            names.append(
                str(
                    _dbus_call(
                        conn,
                        dest,
                        path,
                        ATSPI_ACTION,
                        "GetName",
                        "(s)",
                        GLib.Variant("(i)", (index,)),
                    )
                    or ""
                )
            )
        except Exception:
            names.append("")
    return names


def _do_action(conn: Any, dest: str, path: str, index: int) -> bool:
    try:
        from ulauncher.gi import GLib

        result = _dbus_call(
            conn,
            dest,
            path,
            ATSPI_ACTION,
            "DoAction",
            "(b)",
            GLib.Variant("(i)", (index,)),
        )
    except Exception:
        logger.debug("AT-SPI DoAction failed", exc_info=True)
        return False
    return bool(result) if result is not None else True


def _close_accessible(
    conn: Any,
    dest: str,
    path: str,
    depth: int,
    seen: set[tuple[str, str]],
    budget: list[int],
) -> bool:
    key = (dest, path)
    if key in seen or depth > _CLOSE_WALK_DEPTH or budget[0] <= 0:
        return False
    seen.add(key)
    budget[0] -= 1
    names = _action_names(conn, dest, path)
    role = _accessible_role(conn, dest, path)
    index = pick_close_action(role, _accessible_name(conn, dest, path), names)
    if index is not None:
        return _do_action(conn, dest, path, index)
    if depth >= _CLOSE_WALK_DEPTH or not _should_walk_atspi_role(role, root=depth == 0):
        return False
    try:
        children = _dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetChildren", "(a(so))")
    except Exception:
        return False
    if not isinstance(children, (list, tuple)):
        return False
    for item in children[:12]:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        if _close_accessible(conn, str(item[0] or dest), str(item[1]), depth + 1, seen, budget):
            return True
    return False


def _find_ref_for_title(title: str, app_id: str) -> str:
    needle = (title or "").strip().lower()
    app_needle = (app_id or "").strip().lower()
    for win in list_atspi_windows():
        if needle and (win.title or "").strip().lower() != needle:
            continue
        if app_needle and app_needle not in f"{win.app_id} {win.wm_class}".lower():
            continue
        if win.atspi_ref:
            return win.atspi_ref
    return ""


def _list_atspi_windows() -> list[WindowInfo]:
    conn = _a11y_connection()
    if conn is None:
        return []
    try:
        children = _dbus_call(conn, ATSPI_ROOT_NAME, ATSPI_ROOT_PATH, ATSPI_ACCESSIBLE, "GetChildren", "(a(so))")
    except Exception:
        return []
    if not isinstance(children, (list, tuple)):
        return []
    nodes: list[dict[str, Any]] = []
    for item in children:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        nodes.extend(_windows_for_application(conn, str(item[0]), str(item[1])))
        if len(nodes) >= 64:
            break
    return windows_from_atspi_nodes(nodes)


def _windows_for_application(conn: Any, dest: str, path: str) -> list[dict[str, Any]]:
    try:
        children = _dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetChildren", "(a(so))")
    except Exception:
        return []
    if not isinstance(children, (list, tuple)):
        return []
    pid = _unix_pid_for_name(conn, dest)
    nodes: list[dict[str, Any]] = []
    for item in children:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        node = _read_window_node(conn, str(item[0] or dest), str(item[1]))
        if node is not None:
            node["pid"] = pid
            nodes.append(node)
        if len(nodes) >= 24:
            break
    return nodes


def _unix_pid_for_name(conn: Any, dest: str) -> int:
    """Unix pid of the a11y-bus connection. ext-foreign-toplevel-list has no pid."""
    if not dest:
        return 0
    try:
        from ulauncher.gi import GLib

        pid = _dbus_call(
            conn,
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetConnectionUnixProcessID",
            "(u)",
            GLib.Variant("(s)", (dest,)),
        )
    except Exception:
        logger.debug("AT-SPI unix pid lookup failed", exc_info=True)
        return 0
    try:
        return int(pid or 0)
    except (TypeError, ValueError):
        return 0


def _read_window_node(conn: Any, dest: str, path: str) -> dict[str, Any] | None:
    try:
        role = str(_dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetRoleName", "(s)") or "")
    except Exception:
        return None
    if not atspi_role_is_listed(role) and not atspi_role_is_skip_taskbar(role):
        return None
    active = False
    try:
        active = _state_is_active(_dbus_call(conn, dest, path, ATSPI_ACCESSIBLE, "GetState", "(au)"))
    except Exception:
        logger.debug("AT-SPI GetState failed", exc_info=True)
    return {
        "role": role,
        "title": _accessible_name(conn, dest, path),
        "app_id": dest,
        "bus_name": dest,
        "path": path,
        "active": active,
    }


def _state_is_active(states: Any) -> bool:
    # ATSPI_STATE_ACTIVE is bit 1 of the first uint32 in the at-spi2 bitset.
    if isinstance(states, (list, tuple)) and states:
        try:
            return bool(int(states[0]) & (1 << 1))
        except (TypeError, ValueError):
            return False
    return False
