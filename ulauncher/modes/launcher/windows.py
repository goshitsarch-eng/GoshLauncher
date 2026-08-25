"""Open-window search via EWMH, with wmctrl as a fallback."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Callable
from urllib.parse import quote, unquote

from ulauncher.modes.launcher.number_words import replace_number_words
from ulauncher.modes.launcher.word_match import id_matches_query, text_matches_query

logger = logging.getLogger(__name__)


def window_class_text(wm_class: str = "", wm_instance: str = "", sandboxed_id: str = "") -> str:
    return " ".join(part for part in (wm_class, wm_instance, sandboxed_id) if part)


@dataclass
class WindowInfo:
    wid: str
    title: str
    wm_class: str
    desktop: int
    pid: int = 0
    sticky: bool = False
    user_time: int = 0
    app_id: str = ""
    gtk_app_id: str = ""
    gtk_unique_bus_name: str = ""
    gtk_application_object_path: str = ""
    skip_taskbar: bool = False
    window_type: str = "normal"
    atspi_ref: str = ""


WINDOWS_CACHE_TTL_S = 0.4


class _WindowSnapshot:
    windows: list[WindowInfo] | None = None
    monotonic: float = 0.0
    loading = False
    on_ready: Callable[[], None] | None = None
    pending_idle: Any = None


_window_snapshot = _WindowSnapshot()


class _WorkspaceCountSnapshot:
    value: int | None = None
    loaded = False
    monotonic: float = 0.0


_workspace_count_snapshot = _WorkspaceCountSnapshot()


class _CurrentDesktopSnapshot:
    value: int | str | None = None
    loaded = False
    monotonic: float = 0.0


_current_desktop_snapshot = _CurrentDesktopSnapshot()


def cached_windows() -> list[WindowInfo]:
    return list(_window_snapshot.windows or [])


def windows_cache_is_fresh(now: float | None = None) -> bool:
    if _window_snapshot.windows is None:
        return False
    stamp = time.monotonic() if now is None else now
    return stamp - _window_snapshot.monotonic < WINDOWS_CACHE_TTL_S


def store_window_snapshot(windows: list[WindowInfo], now: float | None = None) -> list[WindowInfo]:
    _window_snapshot.windows = list(windows)
    _window_snapshot.monotonic = time.monotonic() if now is None else now
    _window_snapshot.loading = False
    return list(_window_snapshot.windows)


def invalidate_windows() -> None:
    idle = _window_snapshot.pending_idle
    if idle is not None:
        idle.cancel()
    _window_snapshot.windows = None
    _window_snapshot.monotonic = 0.0
    _window_snapshot.loading = False
    _window_snapshot.on_ready = None
    _window_snapshot.pending_idle = None
    invalidate_workspace_count()


def invalidate_workspace_count() -> None:
    _workspace_count_snapshot.value = None
    _workspace_count_snapshot.loaded = False
    _workspace_count_snapshot.monotonic = 0.0
    invalidate_current_desktop()


def invalidate_current_desktop() -> None:
    _current_desktop_snapshot.value = None
    _current_desktop_snapshot.loaded = False
    _current_desktop_snapshot.monotonic = 0.0


def _refresh_windows() -> None:
    _window_snapshot.pending_idle = None
    list_windows()
    _window_snapshot.loading = False
    callback = _window_snapshot.on_ready
    _window_snapshot.on_ready = None
    if callback:
        callback()


def ensure_windows(on_ready: Callable[[], None]) -> None:
    if windows_cache_is_fresh():
        return
    _window_snapshot.on_ready = on_ready
    if _window_snapshot.loading:
        return
    _window_snapshot.loading = True
    from ulauncher.utils import scheduling

    _window_snapshot.pending_idle = scheduling.run_when_idle(_refresh_windows)


def flush_windows_lookup() -> None:
    idle = _window_snapshot.pending_idle
    if idle is not None:
        idle.cancel()
        _window_snapshot.pending_idle = None
    if not _window_snapshot.loading:
        return
    _refresh_windows()


def _ewmh_windows() -> list[WindowInfo]:
    from ulauncher.utils.ewmh import EWMH

    ewmh = EWMH()
    current = ewmh.getCurrentDesktop()
    results: list[WindowInfo] = []
    for win in reversed(ewmh.getClientListStacking() or []):
        if win is None:
            continue
        try:
            types = ewmh.getWmWindowType(win, str=True) or []
        except Exception:
            types = []
        try:
            states = ewmh.getWmState(win, str=True) or []
        except Exception:
            states = []
        skip_taskbar = "_NET_WM_STATE_SKIP_TASKBAR" in states
        # Docks stay on the list for IME panels (goshos walks St, not alt-tab).
        # Search still hides them via window_is_searchable / shouldListWindow.
        wtype = ewmh_window_type(types)
        name = ewmh.getWmName(win) or ewmh.getWmVisibleName(win) or ""
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        instance = ""
        klass = ""
        try:
            cls = win.get_wm_class()
            if cls:
                instance = str(cls[0] or "") if len(cls) > 0 else ""
                klass = str(cls[1] or "") if len(cls) > 1 else ""
        except Exception:
            instance = ""
            klass = ""
        desktop = ewmh.getWmDesktop(win)
        if desktop is None:
            desktop = current or 0
        sticky = desktop == 0xFFFFFFFF
        pid = ewmh.getWmPid(win) or 0
        gtk_app_id, gtk_bus, gtk_path = _ewmh_gtk_application_props(ewmh, win)
        wm_class = window_class_text(klass, instance, gtk_app_id)
        results.append(
            WindowInfo(
                wid=hex(win.id),
                title=str(name),
                wm_class=wm_class,
                desktop=-1 if sticky else int(desktop),
                pid=int(pid),
                sticky=sticky,
                user_time=_window_user_time(ewmh, win),
                gtk_app_id=gtk_app_id,
                gtk_unique_bus_name=gtk_bus,
                gtk_application_object_path=gtk_path,
                skip_taskbar=skip_taskbar,
                window_type=wtype,
            )
        )
    return results


def _decode_x_string(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").rstrip("\0")
    if isinstance(raw, str):
        return raw.rstrip("\0")
    if isinstance(raw, (list, tuple)):
        try:
            return bytes(raw).decode("utf-8", "replace").rstrip("\0")
        except (TypeError, ValueError, OverflowError):
            return ""
    return str(raw).rstrip("\0")


def _utf8_window_prop(ewmh: Any, win: Any, name: str) -> str:
    getter = getattr(ewmh, "_getProperty", None)
    if not callable(getter):
        return ""
    try:
        return _decode_x_string(getter(name, win))
    except Exception:
        return ""


def _ewmh_gtk_application_props(ewmh: Any, win: Any) -> tuple[str, str, str]:
    return (
        _utf8_window_prop(ewmh, win, "_GTK_APPLICATION_ID"),
        _utf8_window_prop(ewmh, win, "_GTK_UNIQUE_BUS_NAME"),
        _utf8_window_prop(ewmh, win, "_GTK_APPLICATION_OBJECT_PATH"),
    )


def gtk_unique_props_from_mapping(props: Mapping[str, Any]) -> tuple[str, str, str]:
    gtk_app_id = str(
        props.get("gtk-app-id") or props.get("gtk_application_id") or props.get("gtk-application-id") or ""
    )
    gtk_bus = str(
        props.get("gtk-unique-bus-name") or props.get("unique-bus-name") or props.get("gtk_unique_bus_name") or ""
    )
    gtk_path = str(
        props.get("gtk-application-object-path")
        or props.get("application-object-path")
        or props.get("gtk_application_object_path")
        or ""
    )
    return gtk_app_id, gtk_bus, gtk_path


def is_unique_gtk_window(win: WindowInfo) -> bool:
    # gnome-shell shell_app_can_open_new_window: unique bus + object path + app id
    # means a unique GtkApplication that Activate() would only raise.
    return bool(win.gtk_unique_bus_name and win.gtk_application_object_path and win.gtk_app_id)


def _window_user_time(ewmh: Any, win: Any) -> int:
    getter = getattr(ewmh, "_getProperty", None)
    if not callable(getter):
        return 0
    try:
        arr = getter("_NET_WM_USER_TIME", win)
        if isinstance(arr, (list, tuple)) and arr:
            return int(arr[0])
    except Exception:
        return 0
    return 0


def parse_wmctrl_lx(text: str) -> list[WindowInfo]:
    rows: list[WindowInfo] = []
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        wid, desktop_s, wm_class, _host, title = parts
        try:
            desktop = int(desktop_s)
        except ValueError:
            desktop = 0
        rows.append(
            WindowInfo(
                wid=wid,
                title=title,
                wm_class=wm_class,
                desktop=desktop,
                sticky=desktop < 0,
            )
        )
    return rows


_XPROP_LINE_RE = re.compile(r"^([A-Za-z0-9_]+)\([^)]+\)\s*=\s*(.*)$")


def _xprop_unquote(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def parse_xprop_window(text: str) -> dict[str, str]:
    """Parse `xprop -id WID` atoms used for listing and GtkApplication uniqueness."""
    props: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "not found." in stripped:
            continue
        match = _XPROP_LINE_RE.match(stripped)
        if not match:
            continue
        props[match.group(1)] = match.group(2).strip()
    return props


def gtk_unique_props_from_xprop(text: str) -> tuple[str, str, str]:
    props = parse_xprop_window(text)
    return (
        _xprop_unquote(props.get("_GTK_APPLICATION_ID", "")),
        _xprop_unquote(props.get("_GTK_UNIQUE_BUS_NAME", "")),
        _xprop_unquote(props.get("_GTK_APPLICATION_OBJECT_PATH", "")),
    )


def window_inspect_from_xprop(text: str) -> tuple[bool | None, str | None, str, str, str] | None:
    """Return skip-taskbar, type, and Gtk unique muxer props from xprop output."""
    props = parse_xprop_window(text)
    if not props:
        return None
    skip_taskbar = "_NET_WM_STATE_SKIP_TASKBAR" in props.get("_NET_WM_STATE", "")
    type_names = [part.strip() for part in props.get("_NET_WM_WINDOW_TYPE", "").split(",") if part.strip()]
    window_type = ewmh_window_type(type_names) if type_names else None
    gtk_app_id, gtk_bus, gtk_path = gtk_unique_props_from_xprop(text)
    if window_type is None and "_NET_WM_STATE" not in props and not gtk_app_id:
        return None
    return skip_taskbar, window_type or ewmh_window_type([]), gtk_app_id, gtk_bus, gtk_path


def _apply_inspect_gtk(row: WindowInfo, flags: tuple[Any, ...]) -> WindowInfo:
    skip_taskbar = bool(flags[0]) if flags[0] is not None else row.skip_taskbar
    wtype = str(flags[1] or "") if len(flags) > 1 else ""
    gtk_app_id = str(flags[2] or "") if len(flags) >= 5 else ""
    gtk_bus = str(flags[3] or "") if len(flags) >= 5 else ""
    gtk_path = str(flags[4] or "") if len(flags) >= 5 else ""
    wm_class = window_class_text(row.wm_class, "", gtk_app_id) if gtk_app_id else row.wm_class
    return replace(
        row,
        wm_class=wm_class,
        gtk_app_id=gtk_app_id or row.gtk_app_id,
        gtk_unique_bus_name=gtk_bus or row.gtk_unique_bus_name,
        gtk_application_object_path=gtk_path or row.gtk_application_object_path,
        skip_taskbar=skip_taskbar,
        window_type=wtype or row.window_type,
    )


def filter_listed_windows(
    rows: list[WindowInfo],
    inspect: Callable[[str], tuple[Any, ...] | None] | None,
) -> list[WindowInfo]:
    """Mark skip-taskbar and type. Docks stay for IME; search hides them.

    goshos shouldListWindow hides skip-taskbar and docks from window search;
    get_n_windows still counts skip-taskbar. A missing inspect result keeps
    the row: wmctrl is the fallback when the stacking list already failed.
    """
    if inspect is None:
        return list(rows)
    kept: list[WindowInfo] = []
    for row in rows:
        flags = inspect(row.wid)
        if flags is None:
            kept.append(row)
            continue
        skip_taskbar, window_type = flags[0], flags[1]
        if skip_taskbar is None and not window_type:
            kept.append(row)
            continue
        kept.append(_apply_inspect_gtk(row, flags))
    return kept


def window_is_searchable(win: WindowInfo) -> bool:
    """Window-search listing: goshos shouldListWindow hides skip-taskbar and docks."""
    return should_list_window(
        True,
        bool(getattr(win, "skip_taskbar", False)),
        str(getattr(win, "window_type", None) or "normal"),
    )


def _ewmh_inspect_wid(ewmh: Any, wid: str) -> tuple[bool | None, str | None, str, str, str] | None:
    try:
        win_id = int(str(wid), 16) if str(wid).startswith("0x") else int(str(wid))
    except ValueError:
        return None
    try:
        win = ewmh.display.create_resource_object("window", win_id)
        types = ewmh.getWmWindowType(win, str=True) or []
        states = ewmh.getWmState(win, str=True) or []
    except Exception:
        return None
    skip_taskbar = "_NET_WM_STATE_SKIP_TASKBAR" in states
    gtk_app_id, gtk_bus, gtk_path = _ewmh_gtk_application_props(ewmh, win)
    return skip_taskbar, ewmh_window_type(types), gtk_app_id, gtk_bus, gtk_path


def _xprop_inspect_wid(wid: str) -> tuple[bool | None, str | None, str, str, str] | None:
    if not shutil.which("xprop"):
        return None
    try:
        text = subprocess.check_output(
            [
                "xprop",
                "-id",
                str(wid),
                "_NET_WM_STATE",
                "_NET_WM_WINDOW_TYPE",
                "_GTK_APPLICATION_ID",
                "_GTK_UNIQUE_BUS_NAME",
                "_GTK_APPLICATION_OBJECT_PATH",
            ],
            text=True,
            errors="replace",
            timeout=0.08,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return window_inspect_from_xprop(text)


def _wmctrl_windows() -> list[WindowInfo]:
    if not shutil.which("wmctrl"):
        return []
    out = subprocess.check_output(["wmctrl", "-lx"], text=True, errors="replace")
    rows = parse_wmctrl_lx(out)
    ewmh = None
    try:
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
    except Exception:
        ewmh = None

    def inspect(wid: str) -> tuple[Any, ...] | None:
        if ewmh is not None:
            flags = _ewmh_inspect_wid(ewmh, wid)
            if flags is not None:
                return flags
        return _xprop_inspect_wid(wid)

    return filter_listed_windows(rows, inspect)


def window_recency_value(tab_index: int, tab_count: int, user_time: int) -> int:
    if isinstance(tab_index, int) and tab_index >= 0 and tab_count > tab_index:
        return (tab_count - tab_index) * 10**12 + user_time
    return user_time


def sort_windows_most_recent(
    windows: list[WindowInfo],
    get_user_time: Any = None,
    tab_ranks: dict[str, int] | None = None,
) -> list[WindowInfo]:
    # goshos: compositor list order is stacking, not focus. sortWindowsMostRecent
    # orders by getUserTime; tab ranks already store windowRecencyValue(i, n, 0).
    tab_count = (max(tab_ranks.values()) + 1) if tab_ranks else 0

    def recency(win: WindowInfo) -> int:
        stamp = get_user_time(win) if callable(get_user_time) else win.user_time
        if isinstance(stamp, (int, float, str)):
            try:
                user_time = int(stamp or 0)
            except (TypeError, ValueError):
                user_time = 0
        else:
            user_time = 0
        if tab_ranks:
            for key in (
                str(win.wid),
                (win.wm_class or "").lower(),
                (win.app_id or "").lower(),
                (win.title or "").lower(),
            ):
                if key and key in tab_ranks:
                    return window_recency_value(tab_ranks[key], tab_count, 0)
        return user_time

    return sorted(windows, key=recency, reverse=True)


INTROSPECT_DESTS = ("org.gnome.Shell.Introspect", "org.gnome.Shell")
INTROSPECT_PATH = "/org/gnome/Shell/Introspect"
INTROSPECT_IFACE = "org.gnome.Shell.Introspect"


def _introspect_window_type(props: Mapping[str, Any]) -> str:
    raw = props.get("window-type", props.get("type"))
    if isinstance(raw, list):
        names = [str(item) for item in raw if item]
        return ewmh_window_type(names)
    if isinstance(raw, str) and raw:
        return ewmh_window_type([raw])
    # Missing or numeric Mutter enums stay normal so untyped windows still list.
    return ewmh_window_type([])


def _introspect_class_text(props: Mapping[str, Any], app_id: str) -> str:
    # gnome-shell GetWindows: wm-class plus sandboxed-app-id. goshos concatenates
    # those into windowClassText so org.mozilla matches a Firefox window.
    sandboxed = str(props.get("sandboxed-app-id") or props.get("sandboxed_app_id") or "")
    wm_raw = str(props.get("wm-class") or props.get("wm_class") or "")
    instance = str(props.get("wm-class-instance") or props.get("wm_instance") or "")
    text = window_class_text(wm_raw, instance, sandboxed)
    if text:
        return text
    return app_id[:-8] if app_id.endswith(".desktop") else app_id


def windows_from_introspect_payload(payload: Any) -> list[WindowInfo]:
    """Map Mutter Introspect GetWindows onto WindowInfo (Wayland has no EWMH list)."""
    if not isinstance(payload, dict):
        return []
    windows: list[WindowInfo] = []
    for xid, props in payload.items():
        if not isinstance(props, dict):
            continue
        if props.get("is-hidden") or props.get("hidden"):
            continue
        skip_taskbar = bool(props.get("is-skip-taskbar") or props.get("skip-taskbar"))
        has_workspace = props.get("workspace", True)
        if has_workspace is None or has_workspace is False:
            continue
        wtype = _introspect_window_type(props)
        title = str(props.get("title") or "")
        app_id = str(props.get("app-id") or props.get("gtk-app-id") or "")
        wm_class = _introspect_class_text(props, app_id)
        if not title and not wm_class:
            continue
        try:
            pid = int(props.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        try:
            wid = hex(int(xid))
        except (TypeError, ValueError):
            wid = str(xid)
        gtk_app_id, gtk_bus, gtk_path = gtk_unique_props_from_mapping(props)
        desktop, sticky = _introspect_desktop(props)
        windows.append(
            WindowInfo(
                wid=wid,
                title=title,
                wm_class=wm_class,
                desktop=desktop,
                pid=pid,
                sticky=sticky,
                app_id=app_id,
                gtk_app_id=gtk_app_id,
                gtk_unique_bus_name=gtk_bus,
                gtk_application_object_path=gtk_path,
                user_time=1 if props.get("has-focus") or props.get("has_focus") else 0,
                skip_taskbar=skip_taskbar,
                window_type=wtype,
            )
        )
    return windows


def _introspect_desktop(props: Mapping[str, Any]) -> tuple[int, bool]:
    """Mutter GetWindows currently omits workspace; keep integer indexes when present."""
    sticky = bool(props.get("on-all-workspaces") or props.get("is-on-all-workspaces"))
    raw = props.get("workspace", True)
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw, sticky
    return 0, sticky


def tab_ranks_from_introspect_payload(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    focused: list[tuple[Any, Mapping[str, Any]]] = []
    rest: list[tuple[Any, Mapping[str, Any]]] = []
    for xid, props in payload.items():
        props_map: Mapping[str, Any] = props if isinstance(props, dict) else {}
        pair = (xid, props_map)
        if props_map.get("has-focus") or props_map.get("has_focus"):
            focused.append(pair)
        else:
            rest.append(pair)
    ranks: dict[str, int] = {}
    for index, (xid, props_map) in enumerate(focused + rest):
        wm_class = str(props_map.get("wm-class") or props_map.get("app-id") or "").lower()
        if wm_class:
            ranks[wm_class] = index
        sandboxed = str(props_map.get("sandboxed-app-id") or "").lower()
        if sandboxed:
            ranks[sandboxed] = index
        ranks[str(xid)] = index
        if isinstance(xid, int):
            ranks[hex(xid)] = index
    return ranks


_NO_DESKTOP_PREFIXES = ("ext:", "lswt:", "wlr:", "atspi:")
_CHROME_WINDOW_TYPES = frozenset(
    {
        "dock",
        "desktop",
        "toolbar",
        "menu",
        "splash",
        "utility",
        "dropdown_menu",
        "tooltip",
        "notification",
        "combo",
        "dnd",
    }
)


def _wid_key(wid: str) -> str:
    text = str(wid or "").strip().lower()
    if text.startswith("0x"):
        try:
            return hex(int(text, 16))
        except ValueError:
            return text
    if text.isdigit():
        return hex(int(text))
    return text


def _is_x11_wid(wid: str) -> bool:
    text = str(wid or "").strip()
    if text.startswith("0x") or text.startswith("0X"):
        try:
            int(text, 16)
        except ValueError:
            return False
        else:
            return True
    return text.isdigit()


def _desktop_unknown(win: WindowInfo) -> bool:
    if win.sticky or win.desktop not in {0, -1}:
        return False
    text = str(win.wid or "").lower()
    return any(text.startswith(prefix) for prefix in _NO_DESKTOP_PREFIXES)


def _window_class_tokens(win: WindowInfo) -> set[str]:
    blob = " ".join(part for part in (win.wm_class, win.app_id, win.gtk_app_id) if part)
    tokens: set[str] = set()
    for raw in blob.lower().replace("-", " ").replace(".", " ").split():
        if len(raw) >= 2:
            tokens.add(raw)
    return tokens


def _classes_compatible(left: WindowInfo, right: WindowInfo) -> bool:
    tokens_a = _window_class_tokens(left)
    tokens_b = _window_class_tokens(right)
    if not tokens_a or not tokens_b:
        return True
    return bool(tokens_a & tokens_b)


def _window_group_key(win: WindowInfo) -> str | None:
    title = (win.title or "").strip().lower()
    return title or None


def _pick_window_type(primary: str, extra: str) -> str:
    if primary in _CHROME_WINDOW_TYPES:
        return primary
    if extra in _CHROME_WINDOW_TYPES:
        return extra
    if primary == "normal" and extra != "normal":
        return extra
    return primary


def _pick_wid(primary: WindowInfo, extra: WindowInfo) -> str:
    if _is_x11_wid(extra.wid) and not _is_x11_wid(primary.wid):
        return extra.wid
    if compositor_window_argv(extra.wid, "focus") and not compositor_window_argv(primary.wid, "focus"):
        return extra.wid
    return primary.wid


def _pick_desktop(primary: WindowInfo, extra: WindowInfo) -> tuple[int, bool]:
    sticky = primary.sticky or extra.sticky
    if primary.desktop < 0 or extra.desktop < 0 or sticky:
        return -1, True
    if _desktop_unknown(primary) and not _desktop_unknown(extra):
        return extra.desktop, extra.sticky
    return primary.desktop, sticky


def overlay_window_info(primary: WindowInfo, extra: WindowInfo) -> WindowInfo:
    """Copy skip-taskbar, workspace, pid, and GTK unique fields onto one row."""
    desktop, sticky = _pick_desktop(primary, extra)
    wm_class = primary.wm_class if len(primary.wm_class) >= len(extra.wm_class) else extra.wm_class
    return replace(
        primary,
        wid=_pick_wid(primary, extra),
        title=primary.title or extra.title,
        wm_class=wm_class,
        desktop=desktop,
        pid=primary.pid or extra.pid,
        sticky=sticky,
        user_time=max(int(primary.user_time or 0), int(extra.user_time or 0)),
        app_id=primary.app_id or extra.app_id,
        gtk_app_id=primary.gtk_app_id or extra.gtk_app_id,
        gtk_unique_bus_name=primary.gtk_unique_bus_name or extra.gtk_unique_bus_name,
        gtk_application_object_path=primary.gtk_application_object_path or extra.gtk_application_object_path,
        skip_taskbar=primary.skip_taskbar or extra.skip_taskbar,
        window_type=_pick_window_type(primary.window_type, extra.window_type),
        atspi_ref=primary.atspi_ref or extra.atspi_ref,
    )


def _match_extra_by_wid(win: WindowInfo, extra_by_wid: dict[str, int], used: set[int]) -> int | None:
    index = extra_by_wid.get(_wid_key(win.wid))
    if index is None or index in used:
        return None
    return index


def _match_extra_by_pid(win: WindowInfo, extra_by_pid: dict[int, list[int]], used: set[int]) -> int | None:
    if win.pid <= 0:
        return None
    candidates = [index for index in extra_by_pid.get(win.pid, []) if index not in used]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _pair_group_windows(
    base_wins: list[WindowInfo],
    extra_indexes: list[int],
    extra: list[WindowInfo],
    used: set[int],
) -> tuple[list[tuple[WindowInfo, int]], list[WindowInfo]]:
    leftover: list[WindowInfo] = []
    pairs: list[tuple[WindowInfo, int]] = []
    available = [index for index in extra_indexes if index not in used]
    for win in base_wins:
        found: int | None = None
        for index in available:
            if _classes_compatible(win, extra[index]):
                found = index
                break
        if found is None:
            leftover.append(win)
            continue
        available.remove(found)
        pairs.append((win, found))
    return pairs, leftover


def merge_window_lists(base: list[WindowInfo], extra: list[WindowInfo]) -> list[WindowInfo]:
    """Union host snapshots. Overlay X11 skip-taskbar onto ext-foreign rows."""
    if not extra:
        return list(base)
    if not base:
        return list(extra)
    extra_by_wid = {_wid_key(win.wid): index for index, win in enumerate(extra)}
    extra_by_pid: dict[int, list[int]] = {}
    for index, win in enumerate(extra):
        if win.pid > 0:
            extra_by_pid.setdefault(win.pid, []).append(index)
    used: set[int] = set()
    merged: list[WindowInfo] = []
    unmatched: list[WindowInfo] = []
    for win in base:
        index = _match_extra_by_wid(win, extra_by_wid, used)
        if index is None:
            index = _match_extra_by_pid(win, extra_by_pid, used)
        if index is None:
            unmatched.append(win)
            continue
        used.add(index)
        merged.append(overlay_window_info(win, extra[index]))
    extra_groups: dict[str, list[int]] = {}
    for index, win in enumerate(extra):
        key = _window_group_key(win)
        if index in used or key is None:
            continue
        extra_groups.setdefault(key, []).append(index)
    base_groups: dict[str, list[WindowInfo]] = {}
    leftovers: list[WindowInfo] = []
    for win in unmatched:
        key = _window_group_key(win)
        if key is None:
            leftovers.append(win)
            continue
        base_groups.setdefault(key, []).append(win)
    for key, group in base_groups.items():
        pairs, rest = _pair_group_windows(group, extra_groups.get(key, []), extra, used)
        for win, index in pairs:
            used.add(index)
            merged.append(overlay_window_info(win, extra[index]))
        leftovers.extend(rest)
    merged.extend(leftovers)
    merged.extend(win for index, win in enumerate(extra) if index not in used)
    return merged


def pick_window_list(
    ewmh: list[WindowInfo],
    wmctrl: list[WindowInfo],
    introspect: list[WindowInfo],
    compositor: list[WindowInfo] | None = None,
    overlay: list[WindowInfo] | None = None,
) -> list[WindowInfo]:
    native = ewmh or wmctrl
    merged = merge_window_lists(native, introspect)
    merged = merge_window_lists(merged, compositor or [])
    return merge_window_lists(merged, overlay or [])


def windows_from_hypr_clients(payload: Any) -> list[WindowInfo]:
    if not isinstance(payload, list):
        return []
    windows: list[WindowInfo] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("mapped") is False:
            continue
        address = str(item.get("address") or "")
        if not address:
            continue
        title = str(item.get("title") or "")
        klass = str(item.get("class") or item.get("initialClass") or "")
        if not title and not klass:
            continue
        desktop = _compositor_workspace_desktop(item.get("workspace"))
        try:
            pid = int(item.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        try:
            history = item.get("focusHistoryID")
            if history is None:
                history = item.get("focusHistoryId")
            user_time = 10**9 - int(history) if isinstance(history, (int, str)) else 0
        except (TypeError, ValueError):
            user_time = 0
        windows.append(
            WindowInfo(
                wid=f"hypr:{address}",
                title=title,
                wm_class=klass,
                desktop=desktop,
                pid=pid,
                sticky=bool(item.get("pinned")),
                user_time=user_time,
                app_id=klass,
                skip_taskbar=bool(item.get("hidden")),
            )
        )
    return windows


def niri_workspace_idx_by_id(workspaces: Any) -> dict[Any, int]:
    """Map niri workspace unique ids onto 1-based ``idx`` (per-output index)."""
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("workspaces") or workspaces.get("items") or []
    mapping: dict[Any, int] = {}
    if not isinstance(workspaces, list):
        return mapping
    for item in workspaces:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if ident is None:
            continue
        number = _workspace_num(item.get("idx"))
        if number is None or number < 1:
            continue
        mapping[ident] = number
        mapping[str(ident)] = number
    return mapping


def niri_workspace_count(payload: Any) -> int | None:
    """Highest 1-based niri idx, or None when the dump has no numbered workspaces."""
    mapping = niri_workspace_idx_by_id(payload)
    if not mapping:
        return None
    return max(mapping.values())


def niri_focus_user_time(item: Mapping[str, Any]) -> int:
    """niri-ipc 26.4 ``focus_timestamp`` ({secs, nanos}); else ``is_focused``."""
    stamp = item.get("focus_timestamp")
    if isinstance(stamp, dict):
        try:
            secs = int(stamp.get("secs") or 0)
            nanos = int(stamp.get("nanos") or 0)
        except (TypeError, ValueError):
            secs, nanos = 0, 0
        if secs or nanos:
            return secs * 1_000_000_000 + nanos
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        return int(stamp)
    return 1 if item.get("is_focused") else 0


def _niri_window_desktop(workspace_id: Any, idx_by_id: Mapping[Any, int]) -> int:
    if not idx_by_id:
        return _compositor_workspace_desktop(workspace_id)
    idx = idx_by_id.get(workspace_id)
    if idx is None and workspace_id is not None:
        idx = idx_by_id.get(str(workspace_id))
    if idx is None:
        return -1
    return one_based_workspace_desktop(idx)


def windows_from_niri_windows(payload: Any, workspaces: Any = None) -> list[WindowInfo]:
    if not isinstance(payload, list):
        return []
    idx_by_id = niri_workspace_idx_by_id(workspaces)
    windows: list[WindowInfo] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if ident is None:
            continue
        title = str(item.get("title") or "")
        app_id = str(item.get("app_id") or "")
        if not title and not app_id:
            continue
        desktop = _niri_window_desktop(item.get("workspace_id"), idx_by_id)
        try:
            pid = int(item.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        windows.append(
            WindowInfo(
                wid=f"niri:{ident}",
                title=title,
                wm_class=app_id,
                desktop=desktop,
                pid=pid,
                sticky=False,
                user_time=niri_focus_user_time(item),
                app_id=app_id,
            )
        )
    return windows


def windows_from_sway_tree(payload: Any) -> list[WindowInfo]:
    return windows_from_i3ipc_tree(payload, "sway")


def windows_from_i3_tree(payload: Any) -> list[WindowInfo]:
    """i3 and miracle-wm speak the same get_tree shape as Sway, with X11 class props."""
    return windows_from_i3ipc_tree(payload, "i3")


def windows_from_i3ipc_tree(payload: Any, prefix: str) -> list[WindowInfo]:
    windows: list[WindowInfo] = []
    _walk_sway_tree(payload, windows, -1, prefix)
    return windows


def _walk_sway_tree(
    node: Any,
    windows: list[WindowInfo],
    desktop: int,
    prefix: str = "sway",
    skip_taskbar: bool = False,
) -> None:
    if not isinstance(node, dict):
        return
    next_desktop = desktop
    next_skip = skip_taskbar
    if node.get("type") == "workspace":
        name = str(node.get("name") or "")
        if name.startswith("__"):
            next_skip = True
            next_desktop = -1
        else:
            next_desktop = workspace_desktop_from_name(name, node.get("num"))
    state = str(node.get("scratchpad_state") or "none").lower()
    if state not in {"", "none"}:
        next_skip = True
    children = list(node.get("nodes") or []) + list(node.get("floating_nodes") or [])
    is_leaf = not children
    has_window = bool(node.get("pid") or node.get("app_id") or node.get("window_properties"))
    if is_leaf and has_window and node.get("type") in {"con", "floating_con"}:
        props = node.get("window_properties") if isinstance(node.get("window_properties"), dict) else {}
        klass = str(node.get("app_id") or props.get("class") or props.get("instance") or "")
        title = str(node.get("name") or props.get("title") or "")
        if title or klass:
            try:
                pid = int(node.get("pid") or 0)
            except (TypeError, ValueError):
                pid = 0
            windows.append(
                WindowInfo(
                    wid=f"{prefix}:{node.get('id')}",
                    title=title,
                    wm_class=klass,
                    desktop=next_desktop,
                    pid=pid,
                    sticky=bool(node.get("sticky")),
                    user_time=1 if node.get("focused") else 0,
                    app_id=str(node.get("app_id") or klass),
                    skip_taskbar=next_skip,
                )
            )
    for child in children:
        _walk_sway_tree(child, windows, next_desktop, prefix, next_skip)


def compositor_window_argv(wid: str, action: str) -> list[str] | None:
    if ":" not in str(wid):
        return None
    kind, ident = str(wid).split(":", 1)
    if not ident:
        return None
    if kind == "hypr":
        dispatch = "focuswindow" if action == "focus" else "closewindow"
        return ["hyprctl", "dispatch", dispatch, f"address:{ident}"]
    if kind == "sway":
        command = "focus" if action == "focus" else "kill"
        return ["swaymsg", f"[con_id={ident}]", command]
    if kind == "i3":
        command = "focus" if action == "focus" else "kill"
        return ["i3-msg", f"[con_id={ident}]", command]
    if kind == "niri":
        verb = "focus-window" if action == "focus" else "close-window"
        return ["niri", "msg", "action", verb, "--id", ident]
    if kind == "wlr":
        if action != "focus":
            # wlrctl has focus/minimize, not close; SIGTERM can still run.
            return None
        app_id, title = _wlr_ident_parts(ident)
        argv = ["wlrctl", "toplevel", "focus"]
        if app_id:
            argv.append(f"app_id:{app_id}")
        if title:
            argv.append(f"title:{title}")
        return argv if app_id or title else None
    if kind == "kwin":
        verb = "windowactivate" if action == "focus" else "windowclose"
        return ["kdotool", verb, ident]
    if kind == "qtile":
        verb = "focus" if action == "focus" else "kill"
        return ["qtile", "cmd-obj", "-o", "window", ident, "-f", verb]
    return None


def _wlr_ident_parts(ident: str) -> tuple[str, str]:
    encoded_app, sep, encoded_title = ident.partition(" ")
    if not sep:
        return unquote(encoded_app), ""
    return unquote(encoded_app), unquote(encoded_title)


def windows_from_wlrctl_list(text: str) -> list[WindowInfo]:
    """Parse undocumented ``wlrctl toplevel list`` lines: ``app_id: title``."""
    if not text:
        return []
    windows: list[WindowInfo] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or ":" not in raw:
            continue
        app_id, title = raw.split(":", 1)
        app_id = app_id.strip()
        title = title.strip()
        if not app_id and not title:
            continue
        ident = quote(app_id, safe="") + " " + quote(title, safe="")
        windows.append(
            WindowInfo(
                wid=f"wlr:{ident}",
                title=title or app_id,
                wm_class=app_id,
                desktop=0,
                app_id=app_id,
            )
        )
    return windows


def windows_from_lswt_csv(text: str) -> list[WindowInfo]:
    """Parse ``lswt -c tai`` (title, app-id, identifier) from ext-foreign-toplevel-list."""
    if not text:
        return []
    windows: list[WindowInfo] = []
    for row in csv.reader(text.splitlines()):
        if not row:
            continue
        title = row[0].strip() if row else ""
        app_id = row[1].strip() if len(row) > 1 else ""
        ident = row[2].strip() if len(row) > 2 else ""
        if not title and not app_id:
            continue
        wid = f"lswt:{ident}" if ident else f"lswt:{quote(app_id, safe='')} {quote(title, safe='')}"
        windows.append(
            WindowInfo(
                wid=wid,
                title=title or app_id,
                wm_class=app_id,
                desktop=0,
                app_id=app_id,
            )
        )
    return windows


def windows_from_ext_foreign_handles(items: Any) -> list[WindowInfo]:
    """Map ext-foreign-toplevel-list handles onto WindowInfo (GNOME Wayland)."""
    if not isinstance(items, list):
        return []
    windows: list[WindowInfo] = []
    from ulauncher.modes.launcher.wayland_toplevels import ext_foreign_handle_to_window_fields

    for item in items:
        if not isinstance(item, dict):
            continue
        fields = ext_foreign_handle_to_window_fields(item)
        if fields is None:
            continue
        app_id = fields["app_id"]
        windows.append(
            WindowInfo(
                wid=f"ext:{fields['identifier']}",
                title=fields["title"],
                wm_class=window_class_text("", "", app_id) or app_id,
                desktop=0,
                app_id=app_id,
            )
        )
    return windows


KWIN_LIST_SCRIPT = (
    "function desktopOf(c){"
    "if(c.onAllDesktops)return -1;"
    "if(typeof c.desktop==='number')return c.desktop;"
    "var ds=c.desktops;"
    "if(ds&&ds.length){var d=ds[0];"
    "if(typeof d==='number')return d;"
    "if(d&&typeof d.x11DesktopNumber==='number')return d.x11DesktopNumber;}"
    "return 1;}"
    "var clients = workspace.windowList();"
    "for (var i = 0; i < clients.length; i++) {"
    "var c = clients[i];"
    "if (!c || c.desktopWindow) continue;"
    "output_result(JSON.stringify({"
    "id: String(c.internalId),"
    "title: String(c.caption || ''),"
    "app_id: String(c.resourceClass || ''),"
    "desktop: desktopOf(c),"
    "onAllDesktops: Boolean(c.onAllDesktops),"
    "pid: Number(c.pid || 0),"
    "skipTaskbar: Boolean(c.skipTaskbar)"
    "}));"
    "}"
)


def one_based_workspace_desktop(number: int) -> int:
    """Map compositor 1-based ids onto WindowInfo.desktop. Unknown/special is -1."""
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        return -1
    return number - 1


def _workspace_num(num: Any) -> int | None:
    if isinstance(num, bool):
        return None
    if isinstance(num, int):
        return num
    if isinstance(num, str):
        try:
            return int(num.strip())
        except ValueError:
            return None
    return None


def workspace_desktop_from_name(name: str, num: Any = None) -> int:
    """Map a Sway/i3/Qtile workspace name onto WindowInfo.desktop.

    Digit names and i3-style ``2:www`` become 0-based indexes. Named
    workspaces (``code``) have no GNOME-style index, so the label is Switch
    to window rather than the leftover Workspace 1 of desktop 0.
    """
    number = _workspace_num(num)
    if number is not None and number >= 1:
        return one_based_workspace_desktop(number)
    text = str(name or "").strip()
    if text.isdigit():
        return one_based_workspace_desktop(int(text))
    head = text.split(":", 1)[0].strip()
    if head.isdigit():
        return one_based_workspace_desktop(int(head))
    return -1


def _compositor_workspace_desktop(workspace: Any) -> int:
    """Map a Hypr/Niri workspace field onto WindowInfo.desktop.

    Numeric ids stay 1-based. A missing or named value is Switch to window
    instead of the leftover Workspace 1 of a defaulted 1.
    """
    if isinstance(workspace, dict):
        return workspace_desktop_from_name(str(workspace.get("name") or ""), workspace.get("id"))
    number = _workspace_num(workspace)
    if number is not None:
        return one_based_workspace_desktop(number)
    return workspace_desktop_from_name(str(workspace or ""))


def _kwin_placement(item: Mapping[str, Any]) -> tuple[int, bool, int]:
    sticky = bool(item.get("onAllDesktops") or item.get("on_all_desktops"))
    try:
        pid = int(item.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    raw = item.get("desktop")
    if sticky:
        return 0, True, pid
    if raw is None:
        return 0, False, pid
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return 0, False, pid
    if number < 0:
        return 0, True, pid
    if number == 0:
        return 0, False, pid
    return number - 1, False, pid


def windows_from_kwin_dump(payload: Any) -> list[WindowInfo]:
    """Parse kdotool kwinscript JSON lines (or a JSON array) of KWin clients."""
    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                loaded = json.loads(text)
            except ValueError:
                loaded = None
            items = loaded if isinstance(loaded, list) else []
        else:
            items = []
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    items.append(json.loads(line))
                except ValueError:
                    continue
    else:
        return []
    windows: list[WindowInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()
        title = str(item.get("title") or "")
        app_id = str(item.get("app_id") or item.get("resourceClass") or "")
        if not ident or (not title and not app_id):
            continue
        if item.get("desktopWindow") or item.get("desktop_window"):
            continue
        desktop, sticky, pid = _kwin_placement(item)
        windows.append(
            WindowInfo(
                wid=f"kwin:{ident}",
                title=title or app_id,
                wm_class=app_id,
                desktop=desktop,
                pid=pid,
                sticky=sticky,
                app_id=app_id,
                skip_taskbar=bool(item.get("skipTaskbar") or item.get("skip_taskbar")),
            )
        )
    return windows


def windows_from_qtile_windows(payload: Any) -> list[WindowInfo]:
    """Parse ``qtile cmd-obj -f windows`` (Qtile Wayland has no EWMH client list)."""
    if isinstance(payload, dict):
        payload = payload.get("windows") or payload.get("items") or []
    if not isinstance(payload, list):
        return []
    windows: list[WindowInfo] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if ident is None or ident == "":
            continue
        klass_raw = item.get("wm_class")
        if isinstance(klass_raw, (list, tuple)):
            klass = str(klass_raw[-1] if klass_raw else "")
        else:
            klass = str(klass_raw or "")
        title = str(item.get("name") or item.get("title") or "")
        if not title and not klass:
            continue
        desktop = workspace_desktop_from_name(str(item.get("group") or ""))
        try:
            pid = int(item.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        windows.append(
            WindowInfo(
                wid=f"qtile:{ident}",
                title=title or klass,
                wm_class=klass,
                desktop=desktop,
                pid=pid,
                user_time=1 if item.get("focused") else 0,
                app_id=klass,
                skip_taskbar=bool(item.get("minimized") or item.get("hidden")),
            )
        )
    return windows


def compositor_list_commands(
    environ: Mapping[str, str] | None = None,
) -> list[tuple[list[str], Callable[[Any], list[WindowInfo]]]]:
    """Prefer the compositor that owns this session's socket when several CLIs exist."""
    env = os.environ if environ is None else environ
    loaders = (
        ("HYPRLAND_INSTANCE_SIGNATURE", ["hyprctl", "-j", "clients"], windows_from_hypr_clients),
        ("SWAYSOCK", ["swaymsg", "-t", "get_tree"], windows_from_sway_tree),
        ("NIRI_SOCKET", ["niri", "msg", "--json", "windows"], windows_from_niri_windows),
        ("I3SOCK", ["i3-msg", "-t", "get_tree"], windows_from_i3_tree),
    )
    preferred: list[tuple[list[str], Callable[[Any], list[WindowInfo]]]] = []
    rest: list[tuple[list[str], Callable[[Any], list[WindowInfo]]]] = []
    for key, argv, parser in loaders:
        item = (argv, parser)
        if env.get(key):
            preferred.append(item)
        else:
            rest.append(item)
    return preferred + rest


def _json_command(argv: list[str]) -> Any:
    try:
        out = subprocess.check_output(argv, text=True, errors="replace", timeout=0.4)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def _text_command(argv: list[str]) -> str | None:
    try:
        return subprocess.check_output(argv, text=True, errors="replace", timeout=0.4)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _compositor_windows() -> list[WindowInfo]:
    for argv, parser in compositor_list_commands():
        if not shutil.which(argv[0]):
            continue
        payload = _json_command(argv)
        if payload is None:
            continue
        if argv == ["niri", "msg", "--json", "windows"]:
            parsed = windows_from_niri_windows(payload, _json_command(["niri", "msg", "--json", "workspaces"]))
        else:
            parsed = parser(payload)
        if parsed:
            return parsed
    from ulauncher.modes.launcher.wayland_toplevels import list_ext_foreign_toplevels

    ext = windows_from_ext_foreign_handles(list_ext_foreign_toplevels())
    if ext:
        return ext
    if shutil.which("wlrctl"):
        text = _text_command(["wlrctl", "toplevel", "list"])
        if text:
            parsed = windows_from_wlrctl_list(text)
            if parsed:
                return parsed
    if shutil.which("lswt"):
        text = _text_command(["lswt", "-c", "tai"])
        if text:
            parsed = windows_from_lswt_csv(text)
            if parsed:
                return parsed
    if shutil.which("kdotool"):
        text = _text_command(["kdotool", "kwinscript", "--inline", KWIN_LIST_SCRIPT])
        if text:
            parsed = windows_from_kwin_dump(text)
            if parsed:
                return parsed
    if shutil.which("qtile"):
        payload = _json_command(["qtile", "cmd-obj", "-f", "windows"])
        if payload is None:
            payload = _json_command(["qtile", "cmd-obj", "-o", "cmd", "-f", "windows"])
        if payload is not None:
            parsed = windows_from_qtile_windows(payload)
            if parsed:
                return parsed
    return []


def _introspect_windows_payload() -> dict[Any, Any]:
    try:
        from ulauncher.gi import Gio, GLib
    except (ImportError, AttributeError, RuntimeError, OSError):
        return {}
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except Exception:
        return {}
    for dest in INTROSPECT_DESTS:
        try:
            result = bus.call_sync(
                dest,
                INTROSPECT_PATH,
                INTROSPECT_IFACE,
                "GetWindows",
                None,
                GLib.VariantType.new("(a{ta{sv}})"),
                Gio.DBusCallFlags.NONE,
                80,
                None,
            )
            payload = result.unpack()[0]
        except Exception:
            logger.debug("Introspect GetWindows failed on %s", dest, exc_info=True)
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def list_windows() -> list[WindowInfo]:
    ewmh: list[WindowInfo] = []
    try:
        ewmh = _ewmh_windows()
    except Exception:
        logger.debug("EWMH window list failed", exc_info=True)
    wmctrl: list[WindowInfo] = []
    if not ewmh:
        try:
            wmctrl = _wmctrl_windows()
        except (OSError, subprocess.CalledProcessError):
            wmctrl = []
    payload = _introspect_windows_payload()
    introspect = windows_from_introspect_payload(payload)
    compositor = _compositor_windows()
    overlay: list[WindowInfo] = []
    extra_ranks: dict[str, int] = {}
    try:
        from ulauncher.modes.launcher.atspi_windows import atspi_focus_ranks, list_atspi_windows

        overlay = list_atspi_windows()
        extra_ranks = atspi_focus_ranks()
    except Exception:
        logger.debug("AT-SPI window overlay failed", exc_info=True)
    windows = pick_window_list(ewmh, wmctrl, introspect, compositor, overlay)
    ranks = tab_ranks_from_introspect_payload(payload)
    for key, index in extra_ranks.items():
        ranks.setdefault(key, index)
    return store_window_snapshot(sort_windows_most_recent(windows, tab_ranks=ranks or None))


def window_workspace_label(index: int, on_all_workspaces: bool = False) -> str:
    if on_all_workspaces:
        return "On all workspaces"
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        return "Switch to window"
    return f"Workspace {index + 1}"


def _workspace_label(win: WindowInfo) -> str:
    return window_workspace_label(win.desktop, win.sticky)


_SWITCH_WS_RE = re.compile(
    r"^(?:(?:go to|switch to|move to)\s+)?(?:workspace|ws)\s+(\d+)$",
    re.IGNORECASE,
)


def parse_workspace_switch_query(query: str) -> dict[str, int] | None:
    text = replace_number_words(query.strip())
    match = _SWITCH_WS_RE.match(text)
    if not match:
        return None
    number = int(match.group(1))
    if number < 1:
        return None
    return {"index": number - 1, "number": number}


def parse_workspace_query(query: str) -> int | None:
    parsed = parse_workspace_switch_query(query)
    return None if parsed is None else parsed["index"]


def workspace_index_in_range(index: int, workspace_count: int) -> bool:
    return isinstance(index, int) and not isinstance(index, bool) and 0 <= index < workspace_count


def _strip_close_title(title: str) -> str:
    text = title.strip()
    article = re.match(r"^(?:my|the|an?)\s+(.+)$", text, re.IGNORECASE)
    if article:
        text = article.group(1).strip()
    stripped = re.sub(r"\s+(windows?|applications?|apps?)$", "", text, flags=re.IGNORECASE).strip()
    return stripped or text


_GOSHOS_CLOSE_RE = re.compile(
    r"^(close|kill|quit|force-?quit|force\s+quit|force\s+close)\s+(.+)$",
    re.IGNORECASE,
)
_POLITE_RE = re.compile(r"^(?:please\s+|can you\s+|could you\s+)", re.IGNORECASE)


def parse_window_close_query(query: str) -> dict[str, str] | None:
    text = query.strip()
    match = _GOSHOS_CLOSE_RE.match(text)
    if not match:
        return None
    title = _strip_close_title(match.group(2))
    if not title:
        return None
    raw = re.sub(r"[\s-]", "", match.group(1).lower())
    intent = "kill" if raw in {"kill", "forcequit", "forceclose"} else ("quit" if raw == "quit" else "close")
    return {"intent": intent, "title": title}


def should_force_quit_window(intent: str) -> bool:
    return intent == "kill"


def parse_window_intent(query: str) -> tuple[str, str]:
    text = query.strip()
    parsed = parse_window_close_query(_POLITE_RE.sub("", text, count=1))
    if parsed is None:
        return "focus", text
    return parsed["intent"], parsed["title"]


def workspace_label_matches(label: str, query: str) -> bool:
    if not label or not query:
        return False
    q = replace_number_words(query.strip().lower())
    lower = label.lower()
    if lower == "on all workspaces":
        return q in {"sticky", "all"} or q.startswith("on all") or q.startswith("all work")
    numbered = re.fullmatch(r"workspace (\d+)", lower)
    if not numbered:
        return False
    number = numbered.group(1)
    return q in {number, f"workspace {number}", f"ws {number}"}


def workspace_switch_title(number: int) -> str:
    return f"Switch to Workspace {number}"


def workspace_result_id(number: int) -> str:
    return f"workspace:{number}"


def window_result_id(window_id: str, title: str, wm_class: str, description: str) -> str:
    if window_id:
        return window_id
    return f"{title}\0{wm_class}\0{description}"


def window_close_title(intent: str, title: str) -> str:
    if intent == "kill":
        return f"Kill {title}"
    if intent == "quit":
        return f"Quit {title}"
    return f"Close {title}"


def _window_fields_match_all_words(title: str, wm_class: str, query: str) -> bool:
    words = [word for word in query.lower().split() if word]
    if len(words) < 2:
        return False
    # goshos windowMatch.js: title via textMatchesQuery, class via idMatchesQuery
    # on the raw wmClass. Replacing dots with spaces would make "org" match
    # every org.* window because the last token of "org" is "org".
    return all(text_matches_query(title, word) or id_matches_query(wm_class, word) for word in words)


def should_list_window(
    has_workspace: Any,
    skip_taskbar: bool,
    window_type: str,
    listed_types: list[str] | tuple[str, ...] | None = None,
) -> bool:
    # goshos windowMatch.js: closed actors, skip-taskbar, and docks stay out of
    # alt-tab. Empty EWMH type is treated as normal by ewmh_window_type.
    # goshos uses the Meta.Workspace object as a boolean; {} in the JS tests
    # is truthy. Python empty dict is not, so only None/False mean "closed".
    if has_workspace is None or has_workspace is False or skip_taskbar:
        return False
    allowed = listed_types if listed_types is not None else ("normal", "dialog", "modal_dialog")
    return window_type in allowed


def ewmh_window_type(types: list[str] | None) -> str:
    names = [str(raw).replace("_NET_WM_WINDOW_TYPE_", "").lower() for raw in types or [] if raw]
    if "modal_dialog" in names:
        return "modal_dialog"
    if "dialog" in names:
        return "dialog"
    if not names or "normal" in names:
        return "normal"
    return names[0]


def window_matches(win: WindowInfo, query: str) -> bool:
    # goshos windowMatches(title, wmClass, query, workspaceLabel). The shared
    # Workspace N label is not a free-text match; title/class still are, so a
    # window named Workspace Settings must keep matching "workspace".
    if len(query) == 0:
        return True
    if text_matches_query(win.title, query) or id_matches_query(win.wm_class, query):
        return True
    if _window_fields_match_all_words(win.title, win.wm_class, query):
        return True
    return workspace_label_matches(_workspace_label(win), query)


def take_window_results(
    switch_row: dict | None,
    window_rows: list[dict],
    max_results: int,
) -> list[dict]:
    if max_results <= 0:
        return []
    results: list[dict] = []
    if switch_row:
        results.append(switch_row)
    for row in window_rows:
        if len(results) >= max_results:
            break
        results.append(row)
    return results


def parse_wmctrl_desktops(text: str) -> int | None:
    """Count `wmctrl -d` rows. None when the output is not a desktop list."""
    count = 0
    for line in text.splitlines():
        if re.match(r"^\d+\s", line):
            count += 1
    return count or None


def parse_wmctrl_current_desktop(text: str) -> int | None:
    """0-based current desktop from the ``*`` marker in `wmctrl -d`."""
    for line in text.splitlines():
        match = re.match(r"^(\d+)\s+\*", line)
        if match:
            return int(match.group(1))
    return None


def _ewmh_desktop_count() -> int | None:
    try:
        from ulauncher.utils.ewmh import EWMH

        count = EWMH().getNumberOfDesktops()
    except Exception:
        return None
    try:
        number = int(count)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _ewmh_current_desktop() -> int | None:
    try:
        from ulauncher.utils.ewmh import EWMH

        current = EWMH().getCurrentDesktop()
    except Exception:
        return None
    try:
        number = int(current)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _desktop_or_name(desktop: int, name: str) -> int | str | None:
    if desktop >= 0:
        return desktop
    text = str(name or "").strip()
    return text or None


def i3ipc_workspace_count(payload: Any) -> int | None:
    """Highest 1-based Sway/i3 workspace number. Named-only dumps are unknown."""
    if not isinstance(payload, list) or not payload:
        return None
    highest = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name.startswith("__"):
            continue
        desktop = workspace_desktop_from_name(name, item.get("num"))
        if desktop >= 0:
            highest = max(highest, desktop + 1)
    return highest or None


def hypr_workspace_count(payload: Any) -> int | None:
    """Highest 1-based Hypr workspace id. Special (negative) ids do not count."""
    if isinstance(payload, dict):
        payload = payload.get("workspaces") or payload.get("items") or []
    if not isinstance(payload, list) or not payload:
        return None
    highest = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        desktop = _compositor_workspace_desktop(item.get("id"))
        if desktop >= 0:
            highest = max(highest, desktop + 1)
    return highest or None


def _qtile_group_items(payload: Any) -> list[Any] | None:
    if isinstance(payload, dict):
        nested = payload.get("groups")
        if nested is None:
            nested = payload.get("items")
        if isinstance(nested, list):
            return nested
        if isinstance(nested, dict):
            return [{"name": name, **(info if isinstance(info, dict) else {})} for name, info in nested.items()]
        return [{"name": name, **(info if isinstance(info, dict) else {})} for name, info in payload.items()]
    if isinstance(payload, list):
        return payload
    return None


def qtile_workspace_count(payload: Any) -> int | None:
    """Highest 1-based Qtile group number. Named-only dumps are unknown."""
    items = _qtile_group_items(payload)
    if not items:
        return None
    highest = 0
    for item in items:
        if isinstance(item, dict):
            desktop = workspace_desktop_from_name(str(item.get("name") or item.get("id") or ""))
        else:
            desktop = workspace_desktop_from_name(str(item or ""))
        if desktop >= 0:
            highest = max(highest, desktop + 1)
    return highest or None


def niri_current_desktop(payload: Any) -> int | str | None:
    """0-based idx of the focused niri workspace, or its name when idx is missing."""
    if isinstance(payload, dict):
        payload = payload.get("workspaces") or payload.get("items") or []
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict) or not item.get("is_focused"):
            continue
        number = _workspace_num(item.get("idx"))
        name = str(item.get("name") or "")
        if number is not None and number >= 1:
            return one_based_workspace_desktop(number)
        return _desktop_or_name(-1, name)
    return None


def i3ipc_current_desktop(payload: Any) -> int | str | None:
    """Focused Sway/i3 workspace as a 0-based index, or the name when unnumbered."""
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict) or not item.get("focused"):
            continue
        name = str(item.get("name") or "")
        if name.startswith("__"):
            continue
        desktop = workspace_desktop_from_name(name, item.get("num"))
        return _desktop_or_name(desktop, name)
    return None


def hypr_current_desktop(payload: Any) -> int | str | None:
    """Hypr ``activeworkspace`` id as a 0-based index, or the special-workspace name."""
    item: Any = payload
    if isinstance(payload, dict):
        nested = payload.get("activeworkspace")
        if nested is None:
            nested = payload.get("workspace")
        if isinstance(nested, dict):
            item = nested
    elif isinstance(payload, list):
        item = None
        for row in payload:
            if isinstance(row, dict) and row.get("focused"):
                item = row
                break
    else:
        return None
    if not isinstance(item, dict):
        return None
    desktop = _compositor_workspace_desktop(item.get("id"))
    return _desktop_or_name(desktop, str(item.get("name") or ""))


def qtile_current_desktop(payload: Any) -> int | str | None:
    """Visible Qtile group: focused, then screen 0, then any group on a screen."""
    items = _qtile_group_items(payload)
    if not items:
        return None
    current = None
    for item in items:
        info = item if isinstance(item, dict) else {"name": str(item or "")}
        if info.get("focused") or info.get("screen") == 0:
            current = info
            break
    if current is None:
        for item in items:
            info = item if isinstance(item, dict) else {"name": str(item or "")}
            if info.get("screen") is not None:
                current = info
                break
    if current is None:
        return None
    name = str(current.get("name") or current.get("id") or "")
    return _desktop_or_name(workspace_desktop_from_name(name), name)


def _session_mentions(env: Mapping[str, str], token: str) -> bool:
    hay = " ".join(env.get(key) or "" for key in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "XDG_SESSION_DESKTOP"))
    return token.lower() in hay.lower()


def _session_workspace_count(environ: Mapping[str, str] | None = None) -> int | None:
    """Count workspaces from the compositor that owns this session's socket."""
    env = os.environ if environ is None else environ
    if env.get("NIRI_SOCKET") and shutil.which("niri"):
        count = niri_workspace_count(_json_command(["niri", "msg", "--json", "workspaces"]))
        if count is not None:
            return count
    if env.get("SWAYSOCK") and shutil.which("swaymsg"):
        count = i3ipc_workspace_count(_json_command(["swaymsg", "-t", "get_workspaces"]))
        if count is not None:
            return count
    if env.get("I3SOCK") and shutil.which("i3-msg"):
        count = i3ipc_workspace_count(_json_command(["i3-msg", "-t", "get_workspaces"]))
        if count is not None:
            return count
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        count = hypr_workspace_count(_json_command(["hyprctl", "-j", "workspaces"]))
        if count is not None:
            return count
    if _session_mentions(env, "qtile") and shutil.which("qtile"):
        payload = _json_command(["qtile", "cmd-obj", "-f", "groups"])
        if payload is None:
            payload = _json_command(["qtile", "cmd-obj", "-o", "cmd", "-f", "groups"])
        count = qtile_workspace_count(payload)
        if count is not None:
            return count
    return None


def _probe_workspace_count() -> int | None:
    from ulauncher.modes.launcher.wayland_workspaces import list_ext_workspaces

    rows = list_ext_workspaces()
    if rows is not None:
        return len([row for row in rows if not row.get("removed")])
    compositor = _session_workspace_count()
    if compositor is not None:
        return compositor
    if shutil.which("wmctrl"):
        parsed = parse_wmctrl_desktops(_text_command(["wmctrl", "-d"]) or "")
        if parsed is not None:
            return parsed
    return _ewmh_desktop_count()


def listed_workspace_count(now: float | None = None) -> int | None:
    """Known desktop count, or None when every backend failed (do not hide the switch row)."""
    stamp = time.monotonic() if now is None else now
    snap = _workspace_count_snapshot
    if snap.loaded and stamp - snap.monotonic < WINDOWS_CACHE_TTL_S:
        return snap.value
    snap.value = _probe_workspace_count()
    snap.loaded = True
    snap.monotonic = stamp
    return snap.value


def _session_current_desktop(environ: Mapping[str, str] | None = None) -> int | str | None:
    """Active workspace from the compositor that owns this session's socket."""
    env = os.environ if environ is None else environ
    if env.get("NIRI_SOCKET") and shutil.which("niri"):
        desktop = niri_current_desktop(_json_command(["niri", "msg", "--json", "workspaces"]))
        if desktop is not None:
            return desktop
    if env.get("SWAYSOCK") and shutil.which("swaymsg"):
        desktop = i3ipc_current_desktop(_json_command(["swaymsg", "-t", "get_workspaces"]))
        if desktop is not None:
            return desktop
    if env.get("I3SOCK") and shutil.which("i3-msg"):
        desktop = i3ipc_current_desktop(_json_command(["i3-msg", "-t", "get_workspaces"]))
        if desktop is not None:
            return desktop
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        desktop = hypr_current_desktop(_json_command(["hyprctl", "-j", "activeworkspace"]))
        if desktop is not None:
            return desktop
    if _session_mentions(env, "qtile") and shutil.which("qtile"):
        payload = _json_command(["qtile", "cmd-obj", "-f", "groups"])
        if payload is None:
            payload = _json_command(["qtile", "cmd-obj", "-o", "cmd", "-f", "groups"])
        desktop = qtile_current_desktop(payload)
        if desktop is not None:
            return desktop
    return None


def _probe_current_desktop() -> int | str | None:
    from ulauncher.modes.launcher.wayland_workspaces import ext_workspace_current_desktop, list_ext_workspaces

    rows = list_ext_workspaces()
    if rows is not None:
        return ext_workspace_current_desktop(rows)
    compositor = _session_current_desktop()
    if compositor is not None:
        return compositor
    if shutil.which("wmctrl"):
        parsed = parse_wmctrl_current_desktop(_text_command(["wmctrl", "-d"]) or "")
        if parsed is not None:
            return parsed
    return _ewmh_current_desktop()


def listed_current_desktop(now: float | None = None) -> int | str | None:
    """Active desktop, or None when every backend failed.

    goshos liveSearchWatcher repaints on ``active-workspace-changed`` so empty-state
    window recency can update without a keystroke. Window titles stay the same.
    """
    stamp = time.monotonic() if now is None else now
    snap = _current_desktop_snapshot
    if snap.loaded and stamp - snap.monotonic < WINDOWS_CACHE_TTL_S:
        return snap.value
    snap.value = _probe_current_desktop()
    snap.loaded = True
    snap.monotonic = stamp
    return snap.value


def _window_row_icon(win: WindowInfo, apps: Sequence[Any]) -> str:
    try:
        from ulauncher.modes.launcher.apps import window_app_icon
    except Exception:
        return "focus-windows-symbolic"
    return window_app_icon(win, apps)


def match_windows(
    query: str,
    limit: int = 6,
    windows: list[WindowInfo] | None = None,
    workspace_count: int | None = None,
    apps: Sequence[Any] | None = None,
) -> list[dict]:
    intent, rest = parse_window_intent(query)
    workspace = parse_workspace_query(query)
    switch_row = None
    if workspace is not None and intent == "focus":
        count = workspace_count
        if count is None and windows is None:
            count = listed_workspace_count()
        if count is None or workspace_index_in_range(workspace, count):
            switch_row = {
                "kind": "workspace",
                "title": workspace_switch_title(workspace + 1),
                "description": "Workspace",
                "icon": "view-app-grid-symbolic",
                "payload": str(workspace),
                "wid": "",
                "id": workspace_result_id(workspace + 1),
            }
    window_rows: list[dict] = []
    icon_apps = apps
    if icon_apps is None:
        # Injected window lists are tests; skip DesktopAppInfo.get_all() there.
        if windows is None:
            try:
                from ulauncher.modes.launcher.apps import iter_apps

                icon_apps = iter_apps()
            except Exception:
                logger.debug("Desktop apps unavailable for window icons", exc_info=True)
                icon_apps = ()
        else:
            icon_apps = ()
    for win in windows if windows is not None else cached_windows():
        if not window_is_searchable(win):
            continue
        target = rest if intent != "focus" else query
        if not window_matches(win, target):
            continue
        name = win.title or win.wm_class
        title = name if intent == "focus" else window_close_title(intent, name)
        description = _workspace_label(win)
        window_rows.append(
            {
                "kind": intent,
                "title": title,
                "description": description,
                "icon": _window_row_icon(win, icon_apps),
                "payload": win.wid,
                "wid": win.wid,
                "pid": win.pid,
                "wm_class": win.wm_class,
                "app_id": win.app_id or win.gtk_app_id,
                "gtk_unique_bus_name": getattr(win, "gtk_unique_bus_name", "") or "",
                "gtk_application_object_path": getattr(win, "gtk_application_object_path", "") or "",
                "atspi_ref": getattr(win, "atspi_ref", "") or "",
                "window_title": name,
                "id": window_result_id(win.wid, title, win.wm_class, description),
            }
        )
    return take_window_results(switch_row, window_rows, limit)


def _grab_atspi_window(payload: Mapping[str, Any]) -> bool:
    try:
        from ulauncher.modes.launcher.atspi_windows import grab_atspi_focus
    except Exception:
        return False
    return grab_atspi_focus(
        str(payload.get("atspi_ref") or ""),
        str(payload.get("window_title") or payload.get("title") or ""),
        str(payload.get("app_id") or payload.get("wm_class") or ""),
    )


def _close_atspi_window(payload: Mapping[str, Any]) -> bool:
    try:
        from ulauncher.modes.launcher.atspi_windows import atspi_close
    except Exception:
        return False
    # Result title is "Close Firefox"; the real surface name is window_title.
    return atspi_close(
        str(payload.get("atspi_ref") or ""),
        str(payload.get("window_title") or ""),
        str(payload.get("app_id") or payload.get("wm_class") or ""),
    )


def application_bus_name(app_id: str) -> str:
    name = (app_id or "").strip()
    if name.endswith(".desktop"):
        name = name[: -len(".desktop")]
    return name


def application_object_path(bus_name: str) -> str:
    if not bus_name:
        return ""
    return "/" + bus_name.replace(".", "/")


def session_has_x11_window_control(is_x11: bool | None = None) -> bool:
    if is_x11 is None:
        from ulauncher.utils.environment import IS_X11

        is_x11 = IS_X11
    return bool(is_x11)


def gtk_action_names_for_close(intent: str) -> tuple[str, ...]:
    if intent == "quit":
        return ("quit", "app.quit", "close", "win.close")
    return ("close", "win.close")


def gtk_muxer_targets_from_payload(
    payload: Mapping[str, Any],
    desktop_ids: Sequence[str] | None = None,
    startup_classes: Sequence[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(bus_name: str, object_path: str) -> None:
        if not bus_name or not object_path or (bus_name, object_path) in seen:
            return
        seen.add((bus_name, object_path))
        targets.append((bus_name, object_path))

    add(str(payload.get("gtk_unique_bus_name") or ""), str(payload.get("gtk_application_object_path") or ""))
    app_id = str(payload.get("app_id") or payload.get("wm_class") or "")
    for bus_name in desktop_bus_names_for_app_id(app_id, desktop_ids, startup_classes):
        add(bus_name, application_object_path(bus_name))
    return targets


def gtk_muxer_close(
    payload: Mapping[str, Any],
    intent: str = "close",
    activate: Callable[[str, str, str], bool] | None = None,
) -> bool:
    """goshos win.delete for GtkApplication windows that expose org.gtk.Actions."""
    call = activate or _gtk_actions_activate
    for bus_name, object_path in gtk_muxer_targets_from_payload(payload):
        for action in gtk_action_names_for_close(intent):
            if call(bus_name, object_path, action):
                return True
    return False


def _gtk_actions_activate(bus_name: str, object_path: str, action: str) -> bool:
    try:
        from ulauncher.gi import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            bus_name,
            object_path,
            "org.gtk.Actions",
            "Activate",
            GLib.Variant("(sava{sv})", (action, [], {})),
            None,
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
    except Exception:
        logger.debug("org.gtk.Actions %s failed on %s", action, bus_name, exc_info=True)
        return False
    return True


def desktop_bus_names_for_app_id(
    app_id: str,
    desktop_ids: Sequence[str] | None = None,
    startup_classes: Sequence[tuple[str, str]] | None = None,
) -> list[str]:
    """Well-known names to try. Wayland app_id is often ``firefox``, not ``org.mozilla.firefox``."""
    names: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        name = application_bus_name(raw)
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    add(app_id)
    needle = application_bus_name(app_id).lower()
    if len(needle) < 2 or "." in needle:
        return names
    compact = needle.replace("-", "").replace("_", "")
    for ident, wm_class in _desktop_hints(desktop_ids, startup_classes):
        bus = application_bus_name(str(ident or ""))
        if not bus:
            continue
        lower = bus.lower()
        klass = str(wm_class or "").strip().lower()
        if lower == needle or lower.rsplit(".", 1)[-1] == needle:
            add(bus)
            continue
        if klass and (klass == needle or klass.replace("-", "").replace("_", "") == compact):
            add(bus)
    return names


def _desktop_hints(
    desktop_ids: Sequence[str] | None,
    startup_classes: Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    if desktop_ids is not None or startup_classes is not None:
        hints = [(str(ident), "") for ident in desktop_ids or ()]
        hints.extend((str(ident), str(klass)) for ident, klass in startup_classes or ())
        return hints
    return _list_desktop_hints()


def _list_desktop_hints() -> list[tuple[str, str]]:
    try:
        from ulauncher.gi import GioUnix
    except (ImportError, AttributeError, RuntimeError, OSError):
        return []
    try:
        infos = GioUnix.DesktopAppInfo.get_all()
    except Exception:
        logger.debug("DesktopAppInfo.get_all failed", exc_info=True)
        return []
    hints: list[tuple[str, str]] = []
    for info in infos or []:
        try:
            ident = str(info.get_id() or "")
        except Exception:
            logger.debug("DesktopAppInfo.get_id failed", exc_info=True)
            continue
        if not ident:
            continue
        wm_class = ""
        try:
            wm_class = str(info.get_string("StartupWMClass") or "")
        except Exception:
            logger.debug("DesktopAppInfo StartupWMClass failed", exc_info=True)
        hints.append((ident, wm_class))
    return hints


def bus_pid_for_window(
    payload: Mapping[str, Any],
    probe: Callable[[str], int | None] | None = None,
    desktop_ids: Sequence[str] | None = None,
    startup_classes: Sequence[tuple[str, str]] | None = None,
) -> int:
    """Unix pid of the window's D-Bus name. ext-foreign-toplevel-list has no pid."""
    names: list[str] = []
    seen: set[str] = set()
    unique = str(payload.get("gtk_unique_bus_name") or "")
    if unique:
        names.append(unique)
        seen.add(unique)
    app_id = str(payload.get("app_id") or payload.get("wm_class") or "")
    for name in desktop_bus_names_for_app_id(app_id, desktop_ids, startup_classes):
        if name not in seen:
            seen.add(name)
            names.append(name)
    getter = probe or _connection_unix_pid
    for name in names:
        try:
            pid = getter(name)
        except Exception:
            logger.debug("D-Bus pid lookup failed for %s", name, exc_info=True)
            continue
        if pid:
            return int(pid)
    return 0


def _connection_unix_pid(name: str) -> int | None:
    from ulauncher.utils.dbus import get_app_pid

    return get_app_pid(name)


def activate_window(payload: dict, application_activate: Callable[[str], bool] | None = None) -> None:
    kind = payload.get("kind")
    if kind == "workspace":
        _switch_workspace(int(payload["payload"]))
        return
    wid = payload.get("wid") or payload.get("payload") or ""
    pid = int(payload.get("pid") or 0)
    app_id = str(payload.get("app_id") or "")
    compositor_can_focus = compositor_window_argv(str(wid), "focus") is not None
    compositor_can_close = compositor_window_argv(str(wid), "close") is not None
    if kind == "kill":
        # goshos win.kill(). ext-foreign rows have pid 0; the session bus name is the process.
        if pid <= 0:
            pid = bus_pid_for_window(payload)
        if pid:
            _signal_pid(pid, signal.SIGKILL)
        return
    if kind in {"close", "quit"}:
        _close_window(wid)
        closed = compositor_can_close or session_has_x11_window_control()
        if not closed:
            closed = gtk_muxer_close(payload, kind)
        if not closed:
            closed = _close_atspi_window(payload)
        if pid and not closed:
            _signal_pid(pid, signal.SIGTERM)
        return
    _focus_window(wid)
    grabbed = False
    if not compositor_can_focus:
        grabbed = _grab_atspi_window(payload)
    if app_id and not session_has_x11_window_control() and not compositor_can_focus and not grabbed:
        activate = application_activate or _focus_application
        activate(app_id)


def _signal_pid(pid: int, sig: int) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, sig)
    except OSError:
        logger.debug("Could not signal pid %s", pid, exc_info=True)


def _focus_application(app_id: str) -> bool:
    bus_name = application_bus_name(app_id)
    path = application_object_path(bus_name)
    if not bus_name or not path:
        return False
    try:
        from ulauncher.gi import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            bus_name,
            path,
            "org.freedesktop.Application",
            "Activate",
            GLib.Variant("(a{sv})", ({},)),
            None,
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
        return True
    except Exception:
        logger.debug("Application.Activate failed for %s", bus_name, exc_info=True)
        return False


def _focus_window(wid: str) -> None:
    argv = compositor_window_argv(wid, "focus")
    if argv:
        subprocess.run(argv, check=False, capture_output=True)
        return
    if shutil.which("wmctrl"):
        subprocess.run(["wmctrl", "-ia", wid], check=False)
        return
    try:
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
        win_id = int(wid, 16) if str(wid).startswith("0x") else int(wid)
        for win in ewmh.getClientList() or []:
            if win and win.id == win_id:
                ewmh.setActiveWindow(win)
                ewmh.display.flush()
                return
    except Exception:
        logger.debug("Could not focus window %s", wid, exc_info=True)


def _close_window(wid: str) -> None:
    argv = compositor_window_argv(wid, "close")
    if argv:
        subprocess.run(argv, check=False, capture_output=True)
        return
    if shutil.which("wmctrl"):
        subprocess.run(["wmctrl", "-ic", wid], check=False)
        return
    try:
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
        win_id = int(wid, 16) if str(wid).startswith("0x") else int(wid)
        for win in ewmh.getClientList() or []:
            if win and win.id == win_id:
                ewmh.setCloseWindow(win)
                ewmh.display.flush()
                return
    except Exception:
        logger.debug("Could not close window %s", wid, exc_info=True)


def workspace_switch_steps(index: int, *, x11: bool = False) -> list[dict[str, Any]]:
    """Prefer compositor IPC on Wayland; wmctrl/EWMH only work with an X11 root window."""
    number = index + 1
    compositors: list[dict[str, Any]] = [
        {"kind": "kwin", "desktop": number},
        {"kind": "argv", "argv": ["swaymsg", "workspace", "number", str(number)]},
        {"kind": "argv", "argv": ["i3-msg", "workspace", "number", str(number)]},
        {"kind": "argv", "argv": ["hyprctl", "dispatch", "workspace", str(number)]},
        {"kind": "argv", "argv": ["niri", "msg", "action", "focus-workspace", str(number)]},
        {"kind": "argv", "argv": ["qtile", "cmd-obj", "-o", "group", str(number), "-f", "toscreen"]},
        {"kind": "ext-workspace", "index": index},
    ]
    x11_steps: list[dict[str, Any]] = [
        {"kind": "argv", "argv": ["wmctrl", "-s", str(index)]},
        {"kind": "ewmh", "index": index},
    ]
    if x11:
        return x11_steps + compositors
    return compositors + x11_steps


def switch_workspace(
    index: int,
    *,
    x11: bool | None = None,
    which: Callable[[str], str | None] | None = None,
    run: Callable[[list[str]], bool] | None = None,
    kwin: Callable[[int], bool] | None = None,
    ewmh: Callable[[int], bool] | None = None,
    ext_workspace: Callable[[int], bool] | None = None,
) -> str | None:
    use_x11 = session_has_x11_window_control() if x11 is None else x11
    which_fn = which or shutil.which
    run_fn = run or _run_workspace_argv
    kwin_fn = kwin or _kwin_set_current_desktop
    ewmh_fn = ewmh or _ewmh_set_current_desktop
    ext_fn = ext_workspace or _ext_workspace_activate
    for step in workspace_switch_steps(index, x11=use_x11):
        kind = step["kind"]
        if kind == "argv":
            argv = step["argv"]
            if which_fn(argv[0]) and run_fn(argv):
                return str(argv[0])
        elif kind == "kwin":
            if kwin_fn(int(step["desktop"])):
                return "kwin"
        elif kind == "ext-workspace":
            if ext_fn(int(step["index"])):
                return "ext-workspace"
        elif kind == "ewmh":
            if ewmh_fn(int(step["index"])):
                return "ewmh"
    return None


def _ext_workspace_activate(index: int) -> bool:
    from ulauncher.modes.launcher.wayland_workspaces import activate_ext_workspace

    return activate_ext_workspace(index)


def _run_workspace_argv(argv: list[str]) -> bool:
    try:
        completed = subprocess.run(argv, check=False, capture_output=True)
        return completed.returncode == 0
    except OSError:
        return False


def _kwin_set_current_desktop(desktop: int) -> bool:
    try:
        from ulauncher.gi import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.kde.KWin",
            "/KWin",
            "org.kde.KWin",
            "setCurrentDesktop",
            GLib.Variant("(i)", (desktop,)),
            None,
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
        return True
    except Exception:
        return False


def _ewmh_set_current_desktop(index: int) -> bool:
    try:
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
        ewmh.setCurrentDesktop(index)
        ewmh.display.flush()
        return True
    except Exception:
        logger.debug("Could not switch workspace %s via EWMH", index, exc_info=True)
        return False


def _switch_workspace(index: int) -> None:
    if switch_workspace(index) is None:
        logger.debug("Could not switch workspace %s", index)
