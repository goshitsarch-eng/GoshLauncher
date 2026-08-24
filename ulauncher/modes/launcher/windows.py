"""Open-window search via EWMH, with wmctrl as a fallback."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass

from ulauncher.modes.launcher.number_words import replace_number_words
from ulauncher.modes.launcher.word_match import id_matches_query, label_matches_query, text_matches_query

logger = logging.getLogger(__name__)

_CLOSE_RE = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?"
    r"(close|quit|kill|force-?quit|force\s+quit|force\s+close)\s+(.+)$",
    re.IGNORECASE,
)
_WS_RE = re.compile(
    r"^(?:(?:go to|switch to|move to)\s+)?(?:workspace|ws)\s+(.+)$",
    re.IGNORECASE,
)


@dataclass
class WindowInfo:
    wid: str
    title: str
    wm_class: str
    desktop: int
    pid: int = 0
    sticky: bool = False


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
            )
        )
    return results


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


def list_windows() -> list[WindowInfo]:
    try:
        return _ewmh_windows()
    except Exception:
        logger.debug("EWMH window list failed", exc_info=True)
        try:
            return _wmctrl_windows()
        except (OSError, subprocess.CalledProcessError):
            return []


def _workspace_label(win: WindowInfo) -> str:
    if win.sticky or win.desktop < 0:
        return "On all workspaces"
    return f"Workspace {win.desktop + 1}"


def parse_workspace_query(query: str) -> int | None:
    match = _WS_RE.match(query.strip())
    if not match:
        return None
    rest = replace_number_words(match.group(1)).strip()
    if rest.isdigit():
        value = int(rest)
        return value - 1 if value >= 1 else None
    return None


def _strip_close_title(title: str) -> str:
    text = title.strip()
    article = re.match(r"^(?:my|the|an?)\s+(.+)$", text, re.IGNORECASE)
    if article:
        text = article.group(1).strip()
    stripped = re.sub(r"\s+(windows?|applications?|apps?)$", "", text, flags=re.IGNORECASE).strip()
    return stripped or text


def parse_window_intent(query: str) -> tuple[str, str]:
    text = query.strip()
    match = _CLOSE_RE.match(text)
    if not match:
        return "focus", text
    raw = re.sub(r"[\s-]", "", match.group(1).lower())
    intent = "kill" if raw in {"kill", "forcequit", "forceclose"} else ("quit" if raw == "quit" else "close")
    title = _strip_close_title(match.group(2))
    if not title:
        return "focus", text
    return intent, title


def window_matches(win: WindowInfo, query: str) -> bool:
    if not query:
        return False
    q = query.lower()
    if q in {"workspace", "spa"}:
        return False
    if text_matches_query(win.title, query) or label_matches_query(win.title, query):
        return True
    if id_matches_query(win.wm_class.replace(".", " "), query) or id_matches_query(win.wm_class, query):
        return True
    return False


def match_windows(query: str, limit: int = 6) -> list[dict]:
    intent, rest = parse_window_intent(query)
    workspace = parse_workspace_query(query)
    results: list[dict] = []
    if workspace is not None and intent == "focus":
        results.append(
            {
                "kind": "workspace",
                "title": f"Switch to workspace {workspace + 1}",
                "description": "Workspace",
                "icon": "workspace-switcher",
                "payload": str(workspace),
                "wid": "",
            }
        )
    for win in list_windows():
        target = rest if intent != "focus" else query
        if intent == "focus" and workspace is not None and rest.isdigit():
            continue
        if not window_matches(win, target):
            continue
        verb = {"focus": "Switch to", "close": "Close", "quit": "Quit", "kill": "Force quit"}[intent]
        results.append(
            {
                "kind": intent,
                "title": win.title or win.wm_class,
                "description": f"{verb} · {_workspace_label(win)}",
                "icon": "focus-windows",
                "payload": win.wid,
                "wid": win.wid,
                "pid": win.pid,
                "wm_class": win.wm_class,
            }
        )
        if len(results) >= limit:
            break
    return results


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
    if kind == "close":
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
