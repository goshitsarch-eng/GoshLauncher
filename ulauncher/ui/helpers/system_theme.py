from __future__ import annotations

from typing import Any, Callable

from ulauncher.gi import Gio

_INTERFACE_SCHEMA = "org.gnome.desktop.interface"


def _get_interface_settings() -> Gio.Settings | None:
    from ulauncher.utils.gsettings import settings_or_none

    return settings_or_none(_INTERFACE_SCHEMA)


def _has_color_scheme(settings: Gio.Settings) -> bool:
    """Gio.Settings.list_keys is deprecated; ask the schema, which is where the keys live."""
    from ulauncher.utils.gsettings import schema_for_id

    schema = schema_for_id(_INTERFACE_SCHEMA)
    if schema is not None:
        return bool(schema.has_key("color-scheme"))
    return "color-scheme" in set(settings.list_keys())


def system_prefers_dark(interface_settings: Gio.Settings | None = None) -> bool:
    """Return True when the desktop prefers a dark theme."""
    interface_settings = interface_settings or _get_interface_settings()
    if interface_settings is None:
        return False

    if _has_color_scheme(interface_settings) and interface_settings.is_writable("color-scheme"):
        value = interface_settings.get_string("color-scheme")
        if value == "prefer-dark":
            return True
        if value in {"prefer-light", "default"}:
            return False

    return False


class SystemThemeWatcher:
    """Watch GNOME interface settings and emit dark preference updates."""

    def __init__(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change
        self.interface_settings = _get_interface_settings()
        self._handler_ids: list[int] = []

        if self.interface_settings is None:
            return

        if _has_color_scheme(self.interface_settings):
            handler_id = self.interface_settings.connect("changed::color-scheme", self._on_settings_changed)
            self._handler_ids.append(handler_id)

    def start(self) -> None:
        if self.interface_settings is None:
            return
        self._emit()

    def disconnect(self) -> None:
        if self.interface_settings is None:
            return
        for handler_id in self._handler_ids:
            self.interface_settings.disconnect(handler_id)
        self._handler_ids.clear()

    def _on_settings_changed(self, *_args: Any) -> None:
        self._emit()

    def _emit(self) -> None:
        self._on_change(system_prefers_dark(self.interface_settings))
