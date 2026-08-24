"""Keep combo rows in sync with settings, ported from Spotlight-goshos prefsCombo.js."""

from __future__ import annotations

import contextlib
from typing import Any, Callable, Sequence

from ulauncher.utils.eventbus import EventBus

PREFS_SAVED_EVENT = "app:prefs_saved"

POSITION_ITEMS = (
    {"id": "center", "label": "Center"},
    {"id": "top", "label": "Top"},
)
DENSITY_ITEMS = (
    {"id": "comfortable", "label": "Comfortable"},
    {"id": "compact", "label": "Compact"},
)
ORDER_ITEMS = (
    {"id": "default", "label": "Apps first"},
    {"id": "windows-first", "label": "Windows first"},
)


def combo_selected_index(items: Sequence[Any], current_id: str | None) -> int:
    for index, item in enumerate(items):
        item_id = item["id"] if isinstance(item, dict) else getattr(item, "id", None)
        if item_id == current_id:
            return index
    return -1


def combo_should_set(index: int, selected: int) -> bool:
    """goshos: if (index >= 0 && row.selected !== index) row.selected = index."""
    return index >= 0 and selected != index


def combo_item_id(items: Sequence[Any], selected_index: int) -> str | None:
    if selected_index < 0 or selected_index >= len(items):
        return None
    item = items[selected_index]
    item_id = item["id"] if isinstance(item, dict) else getattr(item, "id", None)
    return str(item_id) if item_id is not None else None


def changed_signal(key: str) -> str:
    return f"changed::{key}"


def bind_settings_changed(settings: Any, key: str, widget: Any, handler: Callable[..., Any]) -> int:
    """gio.settings outlives the prefs window; disconnect on widget destroy."""
    handler_id = settings.connect(changed_signal(key), handler)

    def on_destroy(*_args: object) -> None:
        settings.disconnect(handler_id)

    connect = getattr(widget, "connect", None)
    if callable(connect):
        # GTK4 widgets dropped destroy; PreferencesView.unbind_settings is the fallback
        with contextlib.suppress(TypeError):
            connect("destroy", on_destroy)
    return handler_id


def _row_selected(row: Any) -> int:
    if hasattr(row, "selected") and not callable(getattr(row, "get_active", None)):
        return int(row.selected)
    get_active = getattr(row, "get_active", None)
    if callable(get_active):
        return int(get_active())
    return -1


def _row_set_selected(row: Any, index: int) -> None:
    if hasattr(row, "selected") and not callable(getattr(row, "set_active", None)):
        row.selected = index
        return
    row.set_active(index)


def bind_settings_combo(row: Any, settings: Any, key: str, items: Sequence[Any]) -> int:
    """applyLookSettings and a failed theme write must move the combo."""

    def apply(*_args: object) -> None:
        index = combo_selected_index(items, settings.get_string(key))
        if combo_should_set(index, _row_selected(row)):
            _row_set_selected(row, index)

    apply()

    def on_selected(*_args: object) -> None:
        item_id = combo_item_id(items, _row_selected(row))
        if item_id:
            settings.set_string(key, item_id)

    if hasattr(row, "selected") and not callable(getattr(row, "get_active", None)):
        row.connect("notify::selected", on_selected)
    else:
        row.connect("changed", on_selected)
    return bind_settings_changed(settings, key, row, apply)


def dependent_row_sensitive(parent_enabled: bool) -> bool:
    """Application actions need Applications; command runner needs prefix modes."""
    return bool(parent_enabled)


class JsonSettingsSignals:
    """JsonConf Settings as Gio.Settings.connect('changed::key') for the prefs window."""

    def __init__(self, settings: Any, bus: EventBus | None = None) -> None:
        self._settings = settings
        self._bus = bus if bus is not None else EventBus()
        self._next_id = 1
        self._handlers: dict[int, Callable[..., Any]] = {}

    def connect(self, signal: str, handler: Callable[..., Any]) -> int:
        key = signal.split("::", 1)[-1].replace("-", "_")
        hid = self._next_id
        self._next_id += 1

        def wrapper(keys: tuple[str, ...]) -> None:
            if key in keys:
                handler()

        self._handlers[hid] = self._bus.listen(PREFS_SAVED_EVENT, wrapper)
        return hid

    def disconnect(self, hid: int) -> None:
        wrapped = self._handlers.pop(hid, None)
        if wrapped is not None:
            self._bus.off(PREFS_SAVED_EVENT, wrapped)

    def disconnect_all(self) -> None:
        for hid in list(self._handlers):
            self.disconnect(hid)

    def get_string(self, key: str) -> str:
        return str(getattr(self._settings, key.replace("-", "_")))

    def set_string(self, key: str, value: str) -> None:
        self._settings.save({key.replace("-", "_"): value})
