"""Construct ``Gio.Settings`` without aborting when the schema is not installed.

``Gio.Settings.new`` and ``Gio.Settings.new_with_path`` call ``g_error()`` for an unknown
schema id, which aborts the process instead of raising, so ``try``/``except GLib.Error``
around them is dead code. Every schema this app touches is optional - gsettings-desktop-schemas,
gnome-settings-daemon, and mutter are all absent on minimal installs and in sandboxes - so the
schema has to be looked up before it is opened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ulauncher.gi import Gio


def schema_for_id(schema_id: str) -> Gio.SettingsSchema | None:
    """The installed schema, or None. Also the guard callers need before opening it."""
    from ulauncher.gi import Gio

    source = Gio.SettingsSchemaSource.get_default()
    if source is None:
        return None
    return source.lookup(schema_id, True)


def settings_or_none(schema_id: str) -> Gio.Settings | None:
    from ulauncher.gi import Gio

    if schema_for_id(schema_id) is None:
        return None
    return Gio.Settings.new(schema_id)


def settings_with_path_or_none(schema_id: str, path: str) -> Gio.Settings | None:
    from ulauncher.gi import Gio

    if schema_for_id(schema_id) is None:
        return None
    return Gio.Settings.new_with_path(schema_id, path)
