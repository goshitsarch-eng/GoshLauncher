"""Application matching using Spotlight-goshos word rules on desktop entries."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from ulauncher.modes.apps.app_mode import AppMode
from ulauncher.modes.apps.app_rankings import AppRankings
from ulauncher.modes.apps.app_result import ACTION_PREFIX, AppResult
from ulauncher.modes.launcher.app_usage import gnome_app_usage_score
from ulauncher.modes.launcher.word_match import (
    SUBSTRING_MIN,
    id_matches_query,
    keyword_matches_query,
    label_matches_query,
    word_prefix_match,
)

_app_mode = AppMode()
_VARIANT_SUFFIX = re.compile(r"[\s-]+(esr|beta|nightly|dev|canary|stable|preview)$", re.IGNORECASE)


def iter_apps() -> list[AppResult]:
    from ulauncher.modes.launcher.parental import app_is_allowed

    return [app for app in _app_mode.get_triggers() if app_is_allowed(app)]


def app_base_name(name: str) -> str:
    return _VARIANT_SUFFIX.sub("", name.lower()).strip()


def unique_by_base_name(apps: list[Any], limit: int) -> list[Any]:
    if limit <= 0:
        return []
    seen: set[str] = set()
    unique: list[Any] = []
    for app in apps:
        base = app_base_name(getattr(app, "name", "") or getattr(app, "app_id", ""))
        if base in seen:
            continue
        seen.add(base)
        unique.append(app)
        if len(unique) >= limit:
            break
    return unique


def _token_tier(
    name_lower: str, generic_lower: str, id_lower: str, keywords: list[str], desc_lower: str, token: str
) -> int:
    if name_lower.startswith(token):
        return 0
    if word_prefix_match(name_lower, token):
        return 1
    if len(token) >= SUBSTRING_MIN and token in name_lower:
        return 2
    if label_matches_query(generic_lower, token):
        return 3
    if id_matches_query(id_lower, token):
        return 4
    if any(keyword_matches_query(keyword, token) for keyword in keywords):
        return 5
    if len(token) >= SUBSTRING_MIN and label_matches_query(desc_lower, token):
        return 6
    return -1


def app_match_tier(app: Any, query: str) -> int:
    if not query:
        return -1
    q = query.lower()
    name_lower = str(getattr(app, "name", "")).lower()
    generic_lower = str(getattr(app, "generic_name", "") or "").lower()
    id_raw = str(getattr(app, "app_id", "")).lower()
    id_lower = id_raw[:-8] if id_raw.endswith(".desktop") else id_raw
    keywords = list(getattr(app, "keywords", []) or [])
    desc_lower = str(getattr(app, "description", "") or "").lower()

    if name_lower.startswith(q):
        return 0
    if word_prefix_match(name_lower, q):
        return 1
    if len(q) >= SUBSTRING_MIN and q in name_lower:
        return 2
    if label_matches_query(generic_lower, q):
        return 3
    if id_matches_query(id_lower, q):
        return 4
    if any(keyword_matches_query(keyword, q) for keyword in keywords):
        return 5
    if len(q) >= SUBSTRING_MIN and label_matches_query(desc_lower, q):
        return 6

    words = [word for word in q.split() if word]
    if len(words) < 2:
        return -1
    worst = 0
    for word in words:
        tier = _token_tier(name_lower, generic_lower, id_lower, keywords, desc_lower, word)
        if tier < 0:
            return -1
        worst = max(worst, tier)
    return 7 + worst


def app_matches(app: AppResult, query: str) -> bool:
    return app_match_tier(app, query) >= 0


def _launcher_rank(app_id: str) -> int:
    ids = AppRankings.load().get_app_ids()
    try:
        return ids.index(app_id)
    except ValueError:
        return len(ids) + 1


def _usage_sort_key(app_id: str) -> tuple[int, float, int]:
    # goshos searchApps: AppUsage.compare after match tier. Missing usage ranks
    # below any scored id; launcher rankings break ties and cover non-GNOME.
    gnome = gnome_app_usage_score(app_id)
    launcher = _launcher_rank(app_id)
    if gnome is None:
        return (1, 0.0, launcher)
    return (0, -float(gnome), launcher)


def match_apps(query: str, limit: int = 6) -> list[AppResult]:
    scored: list[tuple[int, tuple[int, float, int], AppResult]] = []
    for app in iter_apps():
        try:
            tier = app_match_tier(app, query)
        except Exception:  # noqa: S112
            continue
        if tier < 0:
            continue
        scored.append((tier, _usage_sort_key(getattr(app, "app_id", "")), app))
    scored.sort(key=lambda item: (item[0], item[1]))
    return unique_by_base_name([app for _tier, _rank, app in scored], limit)


def app_row_description(window_count: int) -> str:
    if window_count > 0:
        return "Switch to application"
    return "Application"


def _app_class_needles(app: Any) -> set[str]:
    needles: set[str] = set()
    app_id = str(getattr(app, "app_id", "") or "").lower()
    if app_id.endswith(".desktop"):
        app_id = app_id[:-8]
    if app_id:
        needles.add(app_id)
        needles.add(app_id.split(".")[-1])
    executable = str(getattr(app, "_executable", "") or "").lower()
    if executable:
        needles.add(executable)
    return {needle for needle in needles if needle and needle != "desktop"}


def _window_class_tokens(win: Any) -> set[str]:
    cls = str(getattr(win, "wm_class", "") or "").lower()
    return {part for part in re.split(r"[./\s]", cls) if part}


def _app_matches_window(app: Any, win: Any) -> bool:
    needles = _app_class_needles(app)
    if needles & _window_class_tokens(win):
        return True
    gtk = str(getattr(win, "gtk_app_id", "") or getattr(win, "app_id", "") or "").lower()
    if gtk.endswith(".desktop"):
        gtk = gtk[:-8]
    app_id = str(getattr(app, "app_id", "") or "").lower()
    if app_id.endswith(".desktop"):
        app_id = app_id[:-8]
    return bool(gtk and app_id and gtk == app_id)


def focus_open_windows(app: Any, windows: list[Any] | None = None) -> bool:
    from ulauncher.modes.launcher.windows import activate_window, list_windows

    open_windows = list_windows() if windows is None else windows
    if app_window_count(app, open_windows) <= 0:
        return False
    # goshos Shell.App.activate still raises skip-taskbar-only apps. Prefer a
    # listed window so an IBus panel is not focused when a normal one exists.
    target = None
    for win in open_windows:
        if not _app_matches_window(app, win):
            continue
        if getattr(win, "skip_taskbar", False):
            if target is None:
                target = win
            continue
        target = win
        break
    if target is None:
        return False
    activate_window(
        {
            "kind": "focus",
            "wid": getattr(target, "wid", ""),
            "pid": getattr(target, "pid", 0),
            "payload": getattr(target, "wid", ""),
        }
    )
    return True


def window_app_icon(win: Any, apps: Sequence[Any] | None = None) -> str:
    """goshos windowSearch._windowIcon via Shell.WindowTracker.get_window_app."""
    try:
        scan = apps if apps is not None else iter_apps()
    except Exception:
        return "focus-windows-symbolic"
    for app in scan:
        try:
            if not _app_matches_window(app, win):
                continue
            icon = str(getattr(app, "icon", "") or "")
            if icon:
                return icon
        except Exception:  # noqa: S112
            continue
    return "focus-windows-symbolic"


def app_window_count(app: Any, windows: Sequence[Any] | None = None) -> int:
    if windows is None:
        from ulauncher.modes.launcher.windows import list_windows

        windows = list_windows()
    return sum(1 for win in windows if _app_matches_window(app, win))


def app_is_unique_gtk(app: Any, windows: Sequence[Any] | None) -> bool:
    if not windows:
        return False
    from ulauncher.modes.launcher.windows import is_unique_gtk_window

    matched = False
    for win in windows:
        if not _app_matches_window(app, win):
            continue
        matched = True
        if is_unique_gtk_window(win):
            return True
    if not matched:
        return False
    # Wayland Introspect does not export gtk unique bus names. A reachable
    # org.gtk.Actions muxer on the well-known desktop id is a unique GtkApplication.
    for bus_name, object_path in _app_gtk_muxer_targets(app, windows):
        if probe_gtk_actions(bus_name, object_path) is not None:
            return True
    return False


def home_apps(limit: int) -> list[AppResult]:
    # goshos searchFrequentApps: all usable apps, AppUsage order, then
    # takeUniqueByBaseName. Rankings-only lists hid unused apps and kept
    # Firefox plus Firefox ESR as two empty-state rows.
    usable: list[tuple[tuple[int, float, int], int, AppResult]] = []
    for index, app in enumerate(iter_apps()):
        try:
            app_id = str(getattr(app, "app_id", "") or "")
        except Exception:  # noqa: S112
            continue
        if not app_id:
            continue
        usable.append((_usage_sort_key(app_id), index, app))
    usable.sort(key=lambda item: (item[0], item[1]))
    return unique_by_base_name([app for _rank, _index, app in usable], limit)


def is_new_window_action(action_id: str) -> bool:
    normalized = action_id.lower().replace("_", "-")
    return normalized in {"new-window", "newwindow"}


def new_window_title(app_name: str) -> str:
    return f"New window — {app_name}"


def desktop_action_title(action_name: str, app_name: str) -> str:
    return f"{action_name} — {app_name}"


def action_result_limit(max_results: int, _used_app_rows: int) -> int:
    return max_results


def take_app_actions(actions: list[Any], max_results: int) -> list[Any]:
    if max_results <= 0:
        return []
    return actions[:max_results]


def has_desktop_new_window_action(app: Any) -> bool:
    for key in getattr(app, "actions", None) or {}:
        if key == "launch" or not str(key).startswith(ACTION_PREFIX):
            continue
        if is_new_window_action(str(key)[len(ACTION_PREFIX) :]):
            return True
    return False


def muxer_has_new_window_action(action_names: Sequence[str] | None) -> bool:
    # gnome-shell checks g_action_group_has_action(muxer, "app.new-window")
    # before SingleMainWindow. The remote org.gtk.Actions names omit the prefix.
    for name in action_names or ():
        normalized = str(name).lower().replace("_", "-")
        if normalized in {"new-window", "app.new-window"}:
            return True
    return False


def probe_gtk_actions(bus_name: str, object_path: str) -> list[str] | None:
    """List org.gtk.Actions on a muxer. None means the name is not a Gtk app."""
    if not bus_name or not object_path:
        return None
    try:
        from ulauncher.gi import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            bus_name,
            object_path,
            "org.gtk.Actions",
            "List",
            None,
            GLib.VariantType.new("(as)"),
            Gio.DBusCallFlags.NONE,
            80,
            None,
        )
        return [str(item) for item in result.unpack()[0]]
    except Exception:
        return None


def list_gtk_action_names(bus_name: str, object_path: str) -> list[str]:
    names = probe_gtk_actions(bus_name, object_path)
    return [] if names is None else names


def _app_gtk_muxer_targets(app: Any, windows: Sequence[Any] | None) -> list[tuple[str, str]]:
    from ulauncher.modes.launcher.windows import application_bus_name, application_object_path

    seen: set[tuple[str, str]] = set()
    targets: list[tuple[str, str]] = []

    def add(bus_name: str, object_path: str) -> None:
        if not bus_name or not object_path or (bus_name, object_path) in seen:
            return
        seen.add((bus_name, object_path))
        targets.append((bus_name, object_path))

    for win in windows or ():
        if not _app_matches_window(app, win):
            continue
        add(
            str(getattr(win, "gtk_unique_bus_name", "") or ""),
            str(getattr(win, "gtk_application_object_path", "") or ""),
        )
    bus_name = application_bus_name(str(getattr(app, "app_id", "") or ""))
    add(bus_name, application_object_path(bus_name))
    return targets


def app_muxer_has_new_window(app: Any, windows: Sequence[Any] | None) -> bool:
    if not windows or not any(_app_matches_window(app, win) for win in windows):
        return False
    for bus_name, object_path in _app_gtk_muxer_targets(app, windows):
        if muxer_has_new_window_action(list_gtk_action_names(bus_name, object_path)):
            return True
    return False


def can_open_new_window(
    window_count: int,
    app: Any = None,
    unique_gtk: bool | None = None,
    windows: Sequence[Any] | None = None,
    muxer_new_window: bool | None = None,
) -> bool:
    # goshos: get_n_windows() > 0 && shellApp.can_open_new_window().
    # Port of gnome-shell shell_app_can_open_new_window while running:
    # muxer app.new-window, SingleMainWindow / X-GNOME-SingleWindow, a
    # desktop new-window action, then unique GtkApplication windows.
    if window_count <= 0:
        return False
    if muxer_new_window is None:
        muxer_new_window = app_muxer_has_new_window(app, windows)
    if muxer_new_window:
        return True
    if bool(getattr(app, "single_window", False)):
        return False
    if has_desktop_new_window_action(app):
        return True
    if unique_gtk is None:
        unique_gtk = app_is_unique_gtk(app, windows)
    return not unique_gtk


def open_new_window(app: Any) -> bool:
    from ulauncher.modes.apps.launch_app import launch_app

    app_id = str(getattr(app, "app_id", "") or "")
    if not app_id:
        return False
    for key in getattr(app, "actions", None) or {}:
        if not str(key).startswith(ACTION_PREFIX):
            continue
        action_id = str(key)[len(ACTION_PREFIX) :]
        if is_new_window_action(action_id):
            return launch_app(app_id, action_name=action_id)
    return launch_app(app_id, raise_existing=False)


def app_action_rows(
    app: Any,
    limit: int,
    window_count: int = 0,
    windows: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    rows: list[dict[str, Any]] = []
    if can_open_new_window(window_count, app, windows=windows):
        rows.append(
            {
                "title": new_window_title(app.name),
                "description": "Application action",
                "icon": "application-x-executable-symbolic",
                "app_id": getattr(app, "app_id", ""),
                "action_name": "new-window",
                "synthetic_new_window": True,
            }
        )
        if len(rows) >= limit:
            return take_app_actions(rows, limit)
    for key, meta in (getattr(app, "actions", None) or {}).items():
        if key == "launch" or not str(key).startswith(ACTION_PREFIX):
            continue
        action_id = str(key)[len(ACTION_PREFIX) :]
        if is_new_window_action(action_id):
            continue
        name = (meta or {}).get("name") or action_id
        rows.append(
            {
                "title": desktop_action_title(name, app.name),
                "description": "Application action",
                "icon": "application-x-executable-symbolic",
                "app_id": getattr(app, "app_id", ""),
                "action_name": action_id,
            }
        )
        if len(rows) >= limit:
            break
    return take_app_actions(rows, limit)
