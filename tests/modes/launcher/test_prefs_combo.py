from __future__ import annotations

from ulauncher.modes.launcher.looks import LOOKS
from ulauncher.modes.launcher.prefs_combo import (
    JsonSettingsSignals,
    bind_settings_changed,
    bind_settings_combo,
    combo_item_id,
    combo_selected_index,
    combo_should_set,
    dependent_row_sensitive,
)
from ulauncher.modes.launcher.web import SEARCH_ENGINES
from ulauncher.utils.eventbus import EventBus


def test_combo_selected_index_matches_goshos() -> None:
    pop = next(index for index, look in enumerate(LOOKS) if look["id"] == "popos")
    assert combo_selected_index(LOOKS, "popos") == pop
    assert combo_selected_index(LOOKS, "missing") == -1
    kagi = next(index for index, engine in enumerate(SEARCH_ENGINES) if engine["id"] == "kagi")
    assert combo_selected_index(SEARCH_ENGINES, "kagi") == kagi


def test_combo_should_set_skips_unknown_and_same_index() -> None:
    assert combo_should_set(-1, 0) is False
    assert combo_should_set(2, 2) is False
    assert combo_should_set(2, 0) is True


def test_combo_item_id_reads_selected_row() -> None:
    assert combo_item_id(LOOKS, combo_selected_index(LOOKS, "rofi")) == "rofi"
    assert combo_item_id(LOOKS, -1) is None
    assert combo_item_id(LOOKS, 99) is None


def test_bind_settings_changed_disconnects_on_destroy() -> None:
    disconnected: list[int] = []
    destroy_handler = None

    class Settings:
        def connect(self, signal: str, handler: object) -> int:
            self.signal = signal
            self.handler = handler
            return 7

        def disconnect(self, hid: int) -> None:
            disconnected.append(hid)

    class Widget:
        def connect(self, signal: str, handler: object) -> int:
            nonlocal destroy_handler
            if signal == "destroy":
                destroy_handler = handler
            return 1

    settings = Settings()
    bind_settings_changed(settings, "launcher-theme", Widget(), lambda: None)
    assert settings.signal == "changed::launcher-theme"
    assert destroy_handler is not None
    destroy_handler()
    assert disconnected == [7]


def test_bind_settings_combo_follows_and_writes() -> None:
    stored = {"launcher-theme": "spotlight"}
    handlers: dict[str, object] = {}

    class Settings:
        def get_string(self, key: str) -> str:
            return stored[key]

        def set_string(self, key: str, value: str) -> None:
            stored[key] = value
            handler = handlers.get(f"changed::{key}")
            if callable(handler):
                handler()

        def connect(self, signal: str, handler: object) -> int:
            handlers[signal] = handler
            return 3

        def disconnect(self, hid: int) -> None:
            self.disconnected = hid

    class Row:
        def __init__(self) -> None:
            self.selected = 0
            self.signals: dict[str, object] = {}

        def connect(self, signal: str, handler: object) -> int:
            self.signals[signal] = handler
            return 1

    row = Row()
    bind_settings_combo(row, Settings(), "launcher-theme", LOOKS)
    pop = combo_selected_index(LOOKS, "popos")
    assert row.selected == combo_selected_index(LOOKS, "spotlight")
    stored["launcher-theme"] = "popos"
    apply = handlers["changed::launcher-theme"]
    assert callable(apply)
    apply()
    assert row.selected == pop
    row.selected = combo_selected_index(LOOKS, "rofi")
    selected = row.signals["notify::selected"]
    assert callable(selected)
    selected()
    assert stored["launcher-theme"] == "rofi"


def test_dependent_row_sensitive_matches_features_page() -> None:
    assert dependent_row_sensitive(True) is True
    assert dependent_row_sensitive(False) is False


def test_json_settings_signals_follow_prefs_saved_and_disconnect() -> None:
    class Settings:
        look_id = "spotlight"

        def save(self, payload: dict[str, str]) -> bool:
            self.look_id = payload["look_id"]
            EventBus().emit("app:prefs_saved", tuple(payload))
            return True

    settings = Settings()
    box = JsonSettingsSignals(settings)
    heard: list[str] = []
    hid = box.connect("changed::look_id", lambda: heard.append(box.get_string("look_id")))
    box.set_string("look_id", "popos")
    assert heard == ["popos"]
    box.disconnect(hid)
    box.set_string("look_id", "rofi")
    assert heard == ["popos"]
    box.disconnect_all()
