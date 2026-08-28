from __future__ import annotations

from typing import Any

from ulauncher import paths
from ulauncher.data import JsonConf

_settings_file = f"{paths.CONFIG}/settings.json"


class Settings(JsonConf):
    # Leftover Ulauncher JSON. Goshos navigates with arrows / Ctrl+j k n p, not hjkl.
    arrow_key_aliases: str = ""
    # Leftover Ulauncher JSON. goshos always clears the entry on open.
    auto_resume: bool = False
    base_width: int = 600
    close_on_focus_out: bool = True
    disable_desktop_filters: bool = False
    enable_application_mode: bool = True
    grab_mouse_pointer: bool = True
    hotkey_show_app: str = ""  # Note that this is no longer used, other than for migrating to the DE wrapper
    # Leftover Ulauncher JSON. Goshos activates rows 1-9 with Alt when number hints are on.
    jump_keys: str = "1234567890abcdefghijklmnopqrstuvwxyz"
    keep_alive: bool = True
    layer_shell: bool = True
    # Leftover Ulauncher JSON. Empty-state length uses max_per_category like goshos.
    max_recent_apps: int = 6
    raise_if_started: bool = False
    # goshos popupPosition uses the primary work area, not the pointer monitor.
    render_on_screen: str = "default-monitor"
    show_tray_icon: bool = True
    terminal_command: str = ""
    # Leftover Ulauncher JSON. Popup colors come from look_id / gosh-looks.css, not this.
    theme_name: str = "light"
    tray_icon_name: str = "ulauncher-indicator-symbolic"
    # Leftover Ulauncher JSON. Look CSS owns the popup shadow; this is not applied.
    window_shadow: int = 5
    # Spotlight-goshos launcher providers and chrome
    look_id: str = "spotlight"
    applied_look: str = ""
    popup_position: str = "center"
    row_density: str = "comfortable"
    show_result_numbers: bool = False
    show_section_headers: bool = True
    show_search_icon: bool = True
    show_result_icons: bool = True
    show_descriptions: bool = True
    icon_size: int = 28
    max_per_category: int = 6
    results_max_height: int = 400
    web_search_engine: str = "google"
    result_order: str = "default"
    enable_prefix_modes: bool = True
    enable_url_open: bool = True
    enable_path_open: bool = True
    enable_places: bool = True
    enable_bookmarks: bool = True
    enable_calculator: bool = True
    enable_unit_convert: bool = True
    enable_color_hex: bool = True
    enable_time_date: bool = True
    enable_window_search: bool = True
    enable_system_actions: bool = True
    enable_settings_search: bool = True
    enable_recent_files: bool = True
    enable_command_run: bool = False
    show_web_search: bool = True
    enable_empty_suggestions: bool = True
    enable_app_actions: bool = True
    # Qt UI color scheme: "system" follows the desktop, or force "light"/"dark"
    color_scheme: str = "system"

    # Convert dash to underscore
    def __setitem__(self, key: str, value: Any) -> None:  # type: ignore[override]
        normalized = key.replace("-", "_")
        if normalized == "show_indicator_icon":
            normalized = "show_tray_icon"
        elif normalized == "daemonless":
            normalized = "keep_alive"
            value = not value
        elif normalized == "clear_previous_query":
            normalized = "auto_resume"
            value = not value
        super().__setitem__(normalized, value)

    def get_jump_keys(self) -> list[str]:
        # Leftover Ulauncher JSON helper. Nothing in the GTK4 popup reads this.
        return list(dict.fromkeys(list(self.jump_keys)))

    def is_persistent(self) -> bool:
        """Whether the app should be kept alive after the window is closed.

        Uses systemd when available, falling back to keep_alive.
        """
        from ulauncher.utils.systemd_controller import SystemdController

        status = SystemdController("ulauncher").status()
        if status.can_start:
            return status.is_enabled
        return self.keep_alive

    def save(self, *args: Any, **kwargs: Any) -> bool:
        keys = tuple(dict(*args, **kwargs)) if args or kwargs else ()
        saved = super().save(*args, **kwargs)
        if keys:
            from ulauncher.utils.eventbus import EventBus

            EventBus().emit("app:prefs_saved", keys)
        return saved

    @classmethod
    def load(cls, *, force: bool = False) -> Settings:  # type: ignore[override]
        return super().load(_settings_file, force=force)
