"""Pure-Python freedesktop.org Desktop Entry support.

Replaces Gio.DesktopAppInfo: enumerating installed applications, localized
lookup of Name/GenericName/Comment/Keywords, desktop actions, and the
show-in/hidden filtering rules. See
https://specifications.freedesktop.org/desktop-entry-spec/latest/
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Iterator

from ulauncher import paths

logger = logging.getLogger(__name__)

MAIN_GROUP = "Desktop Entry"
_ESCAPES = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}


def _unescape(value: str) -> str:
    if "\\" not in value:
        return value
    out: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value):
            out.append(_ESCAPES.get(value[i + 1], value[i + 1]))
            i += 2
        else:
            out.append(char)
            i += 1
    return "".join(out)


def _locale_variants() -> list[str]:
    """Locale suffixes to try for localized keys, most specific first (lang_COUNTRY, lang)."""
    locale = os.environ.get("LC_MESSAGES") or os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    locale = locale.split(".")[0].split("@")[0]  # strip encoding and modifier
    if not locale or locale in ("C", "POSIX"):
        return []
    variants = [locale]
    if "_" in locale:
        variants.append(locale.split("_")[0])
    return variants


_LOCALES = _locale_variants()


def _parse_keyfile(path: str) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = groups.setdefault(line[1:-1], {})
                continue
            if current is None or "=" not in line:
                continue
            key, _, value = line.partition("=")
            current.setdefault(key.strip(), value.strip())
    return groups


class DesktopEntry:
    """One parsed .desktop application entry."""

    def __init__(self, entry_id: str, filename: str, groups: dict[str, dict[str, str]]) -> None:
        self.id = entry_id
        self.filename = filename
        self._groups = groups
        self._main = groups.get(MAIN_GROUP, {})

    @classmethod
    def from_file(cls, filename: str, entry_id: str | None = None) -> DesktopEntry | None:
        try:
            groups = _parse_keyfile(filename)
        except OSError:
            return None
        main = groups.get(MAIN_GROUP)
        if not main or main.get("Type", "Application") != "Application":
            return None
        return cls(entry_id or os.path.basename(filename), filename, groups)

    def get_string(self, key: str, group: str = MAIN_GROUP) -> str:
        return _unescape(self._groups.get(group, {}).get(key, ""))

    def get_localized(self, key: str, group: str = MAIN_GROUP) -> str:
        values = self._groups.get(group, {})
        for locale in _LOCALES:
            localized = values.get(f"{key}[{locale}]")
            if localized:
                return _unescape(localized)
        return _unescape(values.get(key, ""))

    def get_boolean(self, key: str, group: str = MAIN_GROUP) -> bool:
        return self._groups.get(group, {}).get(key, "").strip().lower() == "true"

    def get_list(self, key: str, localized: bool = False, group: str = MAIN_GROUP) -> list[str]:
        raw = self.get_localized(key, group) if localized else self.get_string(key, group)
        return [item for item in (part.strip() for part in raw.split(";")) if item]

    # Convenience accessors mirroring what the app code needs

    @property
    def name(self) -> str:
        return self.get_localized("Name")

    @property
    def generic_name(self) -> str:
        return self.get_localized("GenericName")

    @property
    def comment(self) -> str:
        return self.get_localized("Comment")

    @property
    def icon(self) -> str:
        return self.get_string("Icon")

    @property
    def keywords(self) -> list[str]:
        return self.get_list("Keywords", localized=True)

    @property
    def exec_line(self) -> str:
        return self.get_string("Exec")

    @property
    def executable(self) -> str:
        """Basename of TryExec, falling back to the first word of Exec.

        TryExec is what we actually want (name of/path to exec), but it's often not
        specified. Exec is always specified, but the executable it names is sometimes
        a wrapper like "env" or "sh".
        """
        try_exec = self.get_string("TryExec")
        if try_exec:
            return os.path.basename(try_exec)
        try:
            argv = shlex.split(self.exec_line)
        except ValueError:
            return ""
        return os.path.basename(argv[0]) if argv else ""

    @property
    def hidden(self) -> bool:
        return self.get_boolean("Hidden")

    @property
    def no_display(self) -> bool:
        return self.get_boolean("NoDisplay")

    @property
    def terminal(self) -> bool:
        return self.get_boolean("Terminal")

    @property
    def dbus_activatable(self) -> bool:
        return self.get_boolean("DBusActivatable")

    @property
    def single_main_window(self) -> bool:
        return self.get_boolean("SingleMainWindow") or self.get_boolean("X-GNOME-SingleWindow")

    @property
    def working_dir(self) -> str:
        return self.get_string("Path")

    @property
    def startup_wm_class(self) -> str:
        return self.get_string("StartupWMClass")

    def show_in_current_desktop(self) -> bool:
        """OnlyShowIn/NotShowIn filtering against $XDG_CURRENT_DESKTOP."""
        current = {d for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d}
        only_show_in = self.get_list("OnlyShowIn")
        if only_show_in and not current.intersection(only_show_in):
            return False
        not_show_in = self.get_list("NotShowIn")
        return not current.intersection(not_show_in)

    def get_actions(self) -> dict[str, dict[str, str]]:
        """Desktop actions as {action_id: {"name": ..., "exec": ..., "icon": ...}}."""
        actions: dict[str, dict[str, str]] = {}
        for action_id in self.get_list("Actions"):
            group = f"Desktop Action {action_id}"
            if group not in self._groups:
                continue
            name = self.get_localized("Name", group)
            if not name:
                continue
            actions[action_id] = {
                "name": name,
                "exec": self.get_string("Exec", group),
                "icon": self.get_string("Icon", group),
            }
        return actions

    def get_action_exec(self, action_id: str) -> str:
        return self.get_string("Exec", f"Desktop Action {action_id}")


def _application_dirs() -> list[str]:
    dirs = [os.path.join(paths.XDG_DATA_HOME, "applications")]
    dirs.extend(os.path.join(data_dir, "applications") for data_dir in paths.XDG_DATA_DIRS if data_dir)
    seen: set[str] = set()
    unique = []
    for d in dirs:
        real = os.path.normpath(d)
        if real not in seen:
            seen.add(real)
            unique.append(real)
    return unique


def _iter_desktop_files(base_dir: str) -> Iterator[tuple[str, str]]:
    """Yield (desktop_file_id, path) for every .desktop file under base_dir.

    Per spec, the id of a file in a subdirectory joins path components with "-".
    """
    for root, _dirs, files in os.walk(base_dir):
        for file_name in files:
            if not file_name.endswith(".desktop"):
                continue
            full = os.path.join(root, file_name)
            rel = os.path.relpath(full, base_dir)
            yield rel.replace(os.sep, "-"), full


def get_all_desktop_entries() -> list[DesktopEntry]:
    """Every installed application entry, first-found id wins (user dirs shadow system dirs).

    Hidden=true entries count as uninstalled per spec, so they are skipped here rather
    than filtered later.
    """
    entries: dict[str, DesktopEntry] = {}
    for app_dir in _application_dirs():
        if not os.path.isdir(app_dir):
            continue
        for entry_id, path in _iter_desktop_files(app_dir):
            if entry_id in entries:
                continue
            entry = DesktopEntry.from_file(path, entry_id)
            if entry is None:
                continue
            entries[entry_id] = entry
    return [entry for entry in entries.values() if not entry.hidden]


def find_desktop_entry(entry_id: str) -> DesktopEntry | None:
    """Look up one entry by desktop file id (with or without the .desktop suffix)."""
    if not entry_id.endswith(".desktop"):
        entry_id += ".desktop"
    for app_dir in _application_dirs():
        candidate = os.path.join(app_dir, entry_id.replace("-", os.sep))
        # Try the literal filename first ("-" is common in plain ids), then the
        # spec's subdirectory expansion for each "-".
        for path in (os.path.join(app_dir, entry_id), candidate):
            if os.path.isfile(path):
                entry = DesktopEntry.from_file(path, entry_id)
                if entry is not None and not entry.hidden:
                    return entry
    return None
