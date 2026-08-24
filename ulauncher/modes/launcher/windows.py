"""Open-window search via EWMH, with wmctrl as a fallback."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from ulauncher.modes.launcher.number_words import replace_number_words
from ulauncher.modes.launcher.word_match import id_matches_query, label_matches_query, text_matches_query

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    wid: str
    title: str
    wm_class: str
    desktop: int
    pid: int = 0
    sticky: bool = False
    user_time: int = 0


def _ewmh_windows() -> list[WindowInfo]:
    from ulauncher.utils.ewmh import EWMH

    ewmh = EWMH()
    current = ewmh.getCurrentDesktop()
    results: list[WindowInfo] = []
    for win in reversed(ewmh.getClientListStacking() or []):
        if win is None:
            continue
        types = ewmh.getWmWindowType(win, str=True) or []
        skip = {"_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK", "_NET_WM_WINDOW_TYPE_SPLASH"}
        if skip.intersection(types):
            continue
        name = ewmh.getWmName(win) or ewmh.getWmVisibleName(win) or ""
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        wm_class = ""
        try:
            cls = win.get_wm_class()
            if cls:
                wm_class = ".".join(c for c in cls if c)
        except Exception:
            wm_class = ""
        desktop = ewmh.getWmDesktop(win)
        if desktop is None:
            desktop = current or 0
        sticky = desktop == 0xFFFFFFFF
        pid = ewmh.getWmPid(win) or 0
        results.append(
            WindowInfo(
                wid=hex(win.id),
                title=str(name),
                wm_class=wm_class,
                desktop=-1 if sticky else int(desktop),
                pid=int(pid),
                sticky=sticky,
                user_time=_window_user_time(ewmh, win),
            )
        )
    return results


def _window_user_time(ewmh: Any, win: Any) -> int:
    getter = getattr(ewmh, "_getProperty", None)
    if not callable(getter):
        return 0
    try:
        arr = getter("_NET_WM_USER_TIME", win)
        if arr:
            return int(arr[0])
    except Exception:
        return 0
    return 0


def _wmctrl_windows() -> list[WindowInfo]:
    if not shutil.which("wmctrl"):
        return []
    out = subprocess.check_output(["wmctrl", "-lx"], text=True, errors="replace")
    rows: list[WindowInfo] = []
    for line in out.splitlines():
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


def window_recency_value(tab_index: int, tab_count: int, user_time: int) -> int:
    if isinstance(tab_index, int) and tab_index >= 0 and tab_count > tab_index:
        return (tab_count - tab_index) * 10**12 + user_time
    return user_time


def sort_windows_most_recent(
    windows: list[WindowInfo],
    get_user_time: Any = None,
    tab_ranks: dict[str, int] | None = None,
) -> list[WindowInfo]:
    indexed = list(windows)
    count = len(indexed)

    def recency(item: tuple[int, WindowInfo]) -> int:
        index, win = item
        if tab_ranks:
            key = (win.wm_class or "").lower()
            tab_index = tab_ranks.get(key, tab_ranks.get(str(win.wid), index))
        else:
            tab_index = index
        stamp = get_user_time(win) if callable(get_user_time) else win.user_time
        return window_recency_value(tab_index, count, int(stamp or 0))

    return [win for _index, win in sorted(enumerate(indexed), key=recency, reverse=True)]


INTROSPECT_DESTS = ("org.gnome.Shell.Introspect", "org.gnome.Shell")
INTROSPECT_PATH = "/org/gnome/Shell/Introspect"
INTROSPECT_IFACE = "org.gnome.Shell.Introspect"


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
        title = str(props.get("title") or "")
        wm_class = str(props.get("wm-class") or props.get("wm_class") or props.get("app-id") or "")
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
        windows.append(WindowInfo(wid=wid, title=title, wm_class=wm_class, desktop=0, pid=pid))
    return windows


def tab_ranks_from_introspect_payload(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    ranks: dict[str, int] = {}
    for index, (xid, props) in enumerate(payload.items()):
        props_map = props if isinstance(props, dict) else {}
        wm_class = str(props_map.get("wm-class") or props_map.get("app-id") or "").lower()
        if wm_class:
            ranks[wm_class] = index
        ranks[str(xid)] = index
        if isinstance(xid, int):
            ranks[hex(xid)] = index
    return ranks


def pick_window_list(
    ewmh: list[WindowInfo],
    wmctrl: list[WindowInfo],
    introspect: list[WindowInfo],
) -> list[WindowInfo]:
    native = ewmh or wmctrl
    if len(introspect) > len(native):
        return introspect
    return native or introspect


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
    windows = pick_window_list(ewmh, wmctrl, introspect)
    ranks = tab_ranks_from_introspect_payload(payload)
    return sort_windows_most_recent(windows, tab_ranks=ranks or None)


def _workspace_label(win: WindowInfo) -> str:
    if win.sticky or win.desktop < 0:
        return "On all workspaces"
    return f"Workspace {win.desktop + 1}"


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


def window_matches(win: WindowInfo, query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    if q in {"workspace", "spa", "work"}:
        return False
    if text_matches_query(win.title, query) or label_matches_query(win.title, query):
        return True
    if id_matches_query(win.wm_class, query):
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


def match_windows(query: str, limit: int = 6) -> list[dict]:
    intent, rest = parse_window_intent(query)
    workspace = parse_workspace_query(query)
    switch_row = None
    if workspace is not None and intent == "focus":
        switch_row = {
            "kind": "workspace",
            "title": workspace_switch_title(workspace + 1),
            "description": "Workspace",
            "icon": "workspace-switcher-symbolic",
            "payload": str(workspace),
            "wid": "",
            "id": workspace_result_id(workspace + 1),
        }
    window_rows: list[dict] = []
    for win in list_windows():
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
                "icon": "focus-windows-symbolic",
                "payload": win.wid,
                "wid": win.wid,
                "pid": win.pid,
                "wm_class": win.wm_class,
                "id": window_result_id(win.wid, title, win.wm_class, description),
            }
        )
    return take_window_results(switch_row, window_rows, limit)


def activate_window(payload: dict) -> None:
    kind = payload.get("kind")
    if kind == "workspace":
        _switch_workspace(int(payload["payload"]))
        return
    wid = payload.get("wid") or payload.get("payload") or ""
    if kind == "kill":
        pid = int(payload.get("pid") or 0)
        if pid:
            subprocess.run(["kill", "-9", str(pid)], check=False)
        return
    if kind in {"close", "quit"}:
        _close_window(wid)
        return
    _focus_window(wid)


def _focus_window(wid: str) -> None:
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


def _switch_workspace(index: int) -> None:
    if shutil.which("wmctrl"):
        subprocess.run(["wmctrl", "-s", str(index)], check=False)
        return
    try:
        from ulauncher.utils.ewmh import EWMH

        ewmh = EWMH()
        ewmh.setCurrentDesktop(index)
        ewmh.display.flush()
    except Exception:
        logger.debug("Could not switch workspace %s", index, exc_info=True)
