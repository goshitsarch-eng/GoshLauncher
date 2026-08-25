from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from gi.repository import Gdk, Gtk

logger = logging.getLogger(__name__)
footer_notice = "Be aware that keyboard shortcuts may be reserved by, or conflict with your system."

RESPONSES = SimpleNamespace(OK=-5, CLOSE=-7)


class HotkeyDialog(Gtk.Dialog):
    _hotkey = ""

    def __init__(self) -> None:
        super().__init__(title="Set new hotkey", modal=True)
        self.add_buttons("Close", Gtk.ResponseType.CLOSE, "Save", Gtk.ResponseType.OK)
        self.set_response_sensitive(RESPONSES.OK, False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=20, margin_bottom=20, spacing=10)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        self._hotkey_input = Gtk.Entry(editable=False)
        vbox.append(self._hotkey_input)

        notice_label = Gtk.Label(use_markup=True, label=f"<i><small>{footer_notice}</small></i>", wrap=True)
        vbox.append(notice_label)

        content = self.get_content_area()
        content.append(vbox)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self._hotkey_input.add_controller(key_controller)
        self.connect("response", self.handle_response)
        self.present()

    def handle_response(self, _widget: HotkeyDialog, response_id: int) -> None:
        if response_id == RESPONSES.OK:
            self.save_and_close()
        if response_id == RESPONSES.CLOSE:
            self.close()

    def set_hotkey(self, key_name: str = "") -> None:
        from ulauncher.modes.launcher.shortcut import format_accelerator, shortcut_display_label

        self._hotkey = key_name
        label = format_accelerator(key_name) if key_name else shortcut_display_label([])
        self._hotkey_input.set_text(label)
        self._hotkey_input.set_position(-1)
        self.set_response_sensitive(RESPONSES.OK, bool(key_name))

    def close(self) -> None:  # type: ignore[override]
        self._hotkey = ""
        self.set_visible(False)

    def save_and_close(self) -> None:
        self.set_visible(False)

    def on_key_press(self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: int) -> bool:
        from ulauncher.modes.launcher.shortcut import build_accelerator, is_modifier_key_name, modifiers_from_mask

        key_name = Gtk.accelerator_name(keyval, 0)
        if is_modifier_key_name(key_name):
            return True

        if self._hotkey and key_name == "Return":
            self.save_and_close()
            return True

        if self._hotkey and key_name == "BackSpace":
            self.set_hotkey()
            return True

        mods = modifiers_from_mask(
            int(state),
            {
                "super": int(Gdk.ModifierType.SUPER_MASK),
                "control": int(Gdk.ModifierType.CONTROL_MASK),
                "shift": int(Gdk.ModifierType.SHIFT_MASK),
                "alt": int(Gdk.ModifierType.ALT_MASK),
                "meta": int(Gdk.ModifierType.META_MASK),
            },
        )
        if not any(mods.values()):
            return False
        accel = build_accelerator(key_name, mods)
        if accel:
            self.set_hotkey(accel)
            return True
        return False

    def run(self, *args: Any, **kwargs: Any) -> str:
        super().run(*args, **kwargs)
        return self._hotkey
