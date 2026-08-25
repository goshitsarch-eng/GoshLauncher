from __future__ import annotations

import logging
from typing import Any

from gi.repository import Adw, Gdk, Gtk

from ulauncher import api_version, version
from ulauncher.modes.launcher.looks import LOOKS, look_about_subtitle, look_prefs_search_text
from ulauncher.modes.launcher.prefs_combo import (
    DENSITY_ITEMS,
    ORDER_ITEMS,
    POSITION_ITEMS,
    JsonSettingsSignals,
    bind_settings_changed,
    bind_settings_combo,
    combo_selected_index,
    combo_should_set,
    dependent_row_sensitive,
)
from ulauncher.modes.launcher.web import SEARCH_ENGINES, engine_prefs_search_text
from ulauncher.ui.helpers.hotkey_controller import HotkeyController
from ulauncher.ui.preferences.adw_rows import (
    add_button_row,
    add_combo_row,
    add_entry_row,
    add_spin_row,
    add_switch_row,
    plain_action_row,
)
from ulauncher.ui.preferences.page_names import GOSHOS_PAGE_IDS
from ulauncher.utils.environment import IS_X11
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings
from ulauncher.utils.systemd_controller import SystemdController

logger = logging.getLogger(__name__)
events = EventBus()

_PROVIDER_SWITCHES = (
    (
        "enable_calculator",
        "Calculator",
        (
            "Evaluate math including 50%, sqrt, asin, log2, sin 90, 1+2=, 1+2=3, 1 000 + 2, 5!, e+1, =e, "
            "2pi^2, 5 squared, 2 to the power of 8, 2 to the 8th, 2 to the eighth, 2 plus 2, two plus two, "
            "twenty plus two, two million, 2 add 3, 8 subtract 3, half of 80, square root of 16, and 8 over 2 "
            "and copy the result with Enter"
        ),
    ),
    (
        "enable_unit_convert",
        "Unit conversion",
        (
            "10 km to mi, ten km to mi, 10 km into mi, convert 10 km to mi, how many miles in 10 km, "
            "how many miles in ten km, how many km in a mile, a cup to ml, two million km to mi, 1 000 km to mi, "
            "1 cup to tbsp, 1 fl oz to ml, 2 hours to min, 100 kph to mph, 32 psi to bar, 200 kcal to kj, "
            "1 hp to kw, 180 deg to rad, 32 f to c"
        ),
    ),
    (
        "enable_color_hex",
        "Colors",
        (
            "Type #f00, red, rebeccapurple, rgb(255, 0, 0), rgb 255 0 0, rgb 100% 0% 0%, rgba 255 0 0 0.5, "
            "rgb(100%, 0%, 0%), hsl(0deg 100% 50%), hsl 0 100% 50%, hsl(0 100 50), or hwb(0 0% 0%) and press Enter "
            "to copy"
        ),
    ),
    (
        "enable_window_search",
        "Open windows",
        (
            "Switch by title, class, workspace 2, workspace two, workspace twenty, switch to firefox, or "
            "find windows firefox. Type close firefox, close the firefox window, close the firefox application, "
            "can you close firefox, kill firefox, force quit firefox, or force close firefox"
        ),
    ),
    (
        "enable_system_actions",
        "System actions",
        (
            "Lock, suspend, restart, power off, log out, switch user, lock or unlock rotation, screenshot. "
            "lock the screen, lock now, unlock, lock orientation, turn off, power off, sign out, and sign off match"
        ),
    ),
    (
        "enable_settings_search",
        "GNOME Settings",
        (
            "Jump to Settings panels including Privacy & Security. open wifi settings and open display "
            "preferences still find the panel"
        ),
    ),
    ("enable_recent_files", "Recent files", "Open recently used local files and sftp/smb locations"),
    (
        "enable_url_open",
        "Open URLs",
        "Launch typed addresses, domains, sftp/smb locations, and mailto links",
    ),
    (
        "enable_path_open",
        "Open paths",
        (
            "Open ~/ ./ and absolute paths. Directories also offer Open in Terminal including Kitty, Foot, "
            "Ghostty, Alacritty, WezTerm, and Tilix"
        ),
    ),
    (
        "enable_places",
        "Folders",
        (
            "Home, Documents, Downloads, and the other XDG user folders. open my documents, navigate to "
            "downloads, open the pictures folder, and open pictures dir still find those folders"
        ),
    ),
    ("enable_bookmarks", "Bookmarks", "Folders saved in the GTK 3 and GTK 4 bookmark files"),
    (
        "enable_time_date",
        "Time and date",
        (
            "Type time, now, what time is it, what's the time right now, show me the time, tell me the time, "
            "tell me what time it is, date, today, today's date, what day is it, what's the day, tell me the day, "
            "tomorrow, or yesterday to copy the local clock"
        ),
    ),
)


class PreferencesView:
    """Spotlight-goshos preference pages (Shortcut / Appearance / Features / Web Search / About)."""

    def __init__(self) -> None:
        self.settings: Settings = Settings.load()
        self.autostart_pref: SystemdController = SystemdController("ulauncher")
        self._updating_chrome = False
        self._prefs_signals: JsonSettingsSignals | None = None
        self._feature_switches: dict[str, Gtk.Switch] = {}
        self._chrome_switches: dict[str, Gtk.Switch] = {}
        self._hotkey_capturing = False
        self.pages: dict[str, Adw.PreferencesPage] = {
            "shortcut": self._build_shortcut_page(),
            "appearance": self._build_appearance_page(),
            "features": self._build_features_page(),
            "web-search": self._build_web_search_page(),
            "about": self._build_about_page(),
        }
        self._bind_settings_follow()

    def goshos_pages(self) -> list[Adw.PreferencesPage]:
        return [self.pages[key] for key in GOSHOS_PAGE_IDS]

    def unbind_settings(self) -> None:
        box = getattr(self, "_prefs_signals", None)
        if box is not None:
            box.disconnect_all()

    def _bool_toggle(self, attr: str) -> Any:
        def on_toggle(switch: Gtk.Switch, _: Any) -> None:
            if self._updating_chrome:
                return
            self.settings.save({attr: switch.get_active()})
            if attr in ("enable_application_mode", "enable_prefix_modes"):
                self._sync_dependent_switches()

        return on_toggle

    def _int_spin(self, attr: str) -> Any:
        def on_changed(spin: Gtk.SpinButton) -> None:
            if self._updating_chrome:
                return
            self.settings.save({attr: spin.get_value_as_int()})

        return on_changed

    def _feature_switch(self, group: Adw.PreferencesGroup, attr: str, title: str, subtitle: str) -> Gtk.Switch:
        switch = add_switch_row(group, title, subtitle, bool(getattr(self.settings, attr)), self._bool_toggle(attr))
        self._feature_switches[attr] = switch
        return switch

    def _select_combo(self, combo: Adw.ComboRow, items: list, current_id: str | None) -> None:
        index = combo_selected_index(items, current_id)
        selected = int(combo.get_selected())
        if combo_should_set(index, selected):
            combo.set_selected(index)

    def _build_shortcut_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Shortcut", icon_name="preferences-desktop-keyboard-symbolic")
        group = Adw.PreferencesGroup(
            title="Keyboard Shortcut",
            description="Set the shortcut to open GoshLauncher",
        )

        shortcut_row = plain_action_row("Toggle shortcut", "Click here, then press a key combination")
        shortcut_row.set_activatable(True)
        from ulauncher.modes.launcher.shortcut import shortcut_row_label

        accel = HotkeyController.current_accelerator()
        self._hotkey_label = Gtk.Label(
            label=shortcut_row_label([accel], False), halign=Gtk.Align.END, valign=Gtk.Align.CENTER
        )
        shortcut_row.add_suffix(self._hotkey_label)
        self._shortcut_row = shortcut_row
        shortcut_row.connect("activated", lambda *_args: self._on_hotkey_capture_activate())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_hotkey_capture_key)
        shortcut_row.add_controller(keys)
        shortcut_row.connect("notify::has-focus", self._on_hotkey_focus)
        group.add(shortcut_row)

        add_button_row(group, "Reset to default", "Set shortcut to Ctrl+Space", "Reset", self._on_hotkey_reset_clicked)
        if HotkeyController.is_plasma():
            add_button_row(
                group,
                "Plasma shortcuts",
                "Plasma stores the grab in System Settings.",
                "Keyboard settings",
                self._on_hotkey_clicked,
            )
        page.add(group)

        session = Adw.PreferencesGroup(title="Session")
        self._add_background_row(session)
        self._add_tray_icon_row(session)
        add_switch_row(
            session,
            "Close when losing focus",
            "Hide the launcher as soon as another app grabs focus.",
            self.settings.close_on_focus_out,
            self._on_close_focus_toggled,
        )
        add_switch_row(
            session,
            "Grab mouse pointer focus",
            "Capture the pointer so focus-follows-mouse setups do not steal the launcher.",
            self.settings.grab_mouse_pointer,
            self._on_grab_mouse_toggled,
        )
        add_switch_row(
            session,
            "Auto-resume unfinished sessions",
            "If you close without running the query, restore it next time.",
            self.settings.auto_resume,
            self._on_auto_resume_toggled,
        )
        screen_items = (
            {"id": "mouse-pointer-monitor", "label": "The screen with the mouse pointer"},
            {"id": "default-monitor", "label": "The default screen"},
        )
        self._screen_combo = add_combo_row(
            session,
            "Screen to show on",
            "Which monitor presents the launcher when you press the shortcut.",
            screen_items,
            self.settings.render_on_screen,
        )
        self._screen_items = screen_items
        self._screen_combo.connect("notify::selected", self._on_screen_changed)
        page.add(session)
        return page

    def _add_background_row(self, group: Adw.PreferencesGroup) -> None:
        footer = " Recommended: this makes the launcher open noticeably faster."
        autostart_status = self.autostart_pref.status()
        if autostart_status.can_start:
            desc = "Start automatically with your desktop session so it's ready when you need it." + footer
            add_switch_row(group, "Run in background", desc, autostart_status.is_enabled, self._on_autostart_toggled)
            return
        desc = "Keep running in the background after first use so it stays ready" + footer
        add_switch_row(group, "Run in background", desc, self.settings.keep_alive, self._on_keep_alive_toggled)

    def _add_tray_icon_row(self, group: Adw.PreferencesGroup) -> None:
        self._tray_switch = add_switch_row(
            group,
            "Show tray icon",
            "StatusNotifierItem tray while the launcher is set to run in the background.",
            self.settings.show_tray_icon,
            self._on_tray_toggled,
        )
        self._tray_switch.set_sensitive(self.settings.is_persistent())

    def _build_appearance_page(self) -> Adw.PreferencesPage:
        from ulauncher.modes.launcher.chrome_size import (
            ICON_SIZE_MAX,
            ICON_SIZE_MIN,
            ICON_SIZE_PAGE,
            ICON_SIZE_STEP,
            MAX_RESULTS_MAX,
            MAX_RESULTS_MIN,
            MAX_RESULTS_PAGE,
            MAX_RESULTS_STEP,
            POPUP_WIDTH_MAX,
            POPUP_WIDTH_MIN,
            POPUP_WIDTH_PAGE,
            POPUP_WIDTH_STEP,
            RESULTS_HEIGHT_MAX,
            RESULTS_HEIGHT_MIN,
            RESULTS_HEIGHT_PAGE,
            RESULTS_HEIGHT_STEP,
            clamp_icon_size,
            clamp_max_results,
            clamp_popup_width,
            clamp_results_max_height,
        )

        page = Adw.PreferencesPage(title="Appearance", icon_name="preferences-desktop-appearance-symbolic")
        look_group = Adw.PreferencesGroup(title="Look", description=look_prefs_search_text())
        look_id = getattr(self.settings, "look_id", "spotlight")
        current = next((look for look in LOOKS if look["id"] == look_id), LOOKS[0])
        self._look_combo = add_combo_row(look_group, "Launcher look", current["description"], LOOKS, current["id"])
        self._look_combo.connect("notify::selected", self._on_look_selected)

        self._position_combo = add_combo_row(
            look_group,
            "Position",
            "Center stays put and grows down. Top matches Pop!_OS and KRunner",
            list(POSITION_ITEMS),
            self.settings.popup_position,
        )
        self._density_combo = add_combo_row(
            look_group, "Row density", "", list(DENSITY_ITEMS), self.settings.row_density
        )
        self._order_combo = add_combo_row(
            look_group,
            "Result order",
            "Windows first matches the Pop!_OS launcher",
            list(ORDER_ITEMS),
            self.settings.result_order,
        )
        add_button_row(
            look_group,
            "Reset look",
            (
                "Restore this look's position, density, headers, icons, descriptions, number hints, "
                "icon size, and result order"
            ),
            "Reset",
            self._on_reset_look_clicked,
        )
        page.add(look_group)

        size_group = Adw.PreferencesGroup(title="Size")
        self._width_spin = add_spin_row(
            size_group,
            "Popup width",
            "Width in pixels",
            Gtk.Adjustment(
                value=clamp_popup_width(self.settings.base_width),
                lower=POPUP_WIDTH_MIN,
                upper=POPUP_WIDTH_MAX,
                step_increment=POPUP_WIDTH_STEP,
                page_increment=POPUP_WIDTH_PAGE,
            ),
            self._on_width_changed,
        )
        self._height_spin = add_spin_row(
            size_group,
            "Results max height",
            "Scroll after this height",
            Gtk.Adjustment(
                value=clamp_results_max_height(self.settings.results_max_height),
                lower=RESULTS_HEIGHT_MIN,
                upper=RESULTS_HEIGHT_MAX,
                step_increment=RESULTS_HEIGHT_STEP,
                page_increment=RESULTS_HEIGHT_PAGE,
            ),
            self._int_spin("results_max_height"),
        )
        self._max_spin = add_spin_row(
            size_group,
            "Max results per category",
            "",
            Gtk.Adjustment(
                value=clamp_max_results(self.settings.max_per_category),
                lower=MAX_RESULTS_MIN,
                upper=MAX_RESULTS_MAX,
                step_increment=MAX_RESULTS_STEP,
                page_increment=MAX_RESULTS_PAGE,
            ),
            self._int_spin("max_per_category"),
        )
        self._icon_spin = add_spin_row(
            size_group,
            "Result icon size",
            "Pixels. Compact density still shrinks this",
            Gtk.Adjustment(
                value=clamp_icon_size(self.settings.icon_size),
                lower=ICON_SIZE_MIN,
                upper=ICON_SIZE_MAX,
                step_increment=ICON_SIZE_STEP,
                page_increment=ICON_SIZE_PAGE,
            ),
            self._int_spin("icon_size"),
        )
        page.add(size_group)

        chrome_group = Adw.PreferencesGroup(title="Chrome")
        for attr, title, description in (
            ("show_search_icon", "Search icon", "Magnifying glass in the entry. Hiding it still keeps the query inset"),
            ("show_section_headers", "Section headers", "Category labels above result groups"),
            ("show_result_icons", "Result icons", ""),
            ("show_descriptions", "Result descriptions", ""),
            ("show_result_numbers", "Number hints", "Show 1-9 and activate with Alt+digit"),
        ):
            switch = add_switch_row(
                chrome_group, title, description, bool(getattr(self.settings, attr)), self._bool_toggle(attr)
            )
            self._chrome_switches[attr] = switch
        page.add(chrome_group)
        return page

    def _build_features_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Features", icon_name="preferences-system-symbolic")
        providers = Adw.PreferencesGroup(
            title="Search providers",
            description="Turn individual result types on or off",
        )
        self._feature_switch(
            providers,
            "enable_application_mode",
            "Applications",
            "Installed apps ranked by match quality and usage. open firefox, open up firefox, start up firefox, "
            "fire up firefox, execute firefox, chrome browser, find firefox, search for firefox, and find windows "
            "firefox still find the app. open source stays a name",
        )
        self._app_actions_switch = self._feature_switch(
            providers,
            "enable_app_actions",
            "Application actions",
            "New window and desktop-file actions for the best app match. Applications must stay enabled",
        )
        self._app_actions_switch.set_sensitive(dependent_row_sensitive(self.settings.enable_application_mode))
        for attr, title, description in _PROVIDER_SWITCHES:
            self._feature_switch(providers, attr, title, description)
        self._command_switch = self._feature_switch(
            providers,
            "enable_command_run",
            "Command runner",
            "Run a PATH or file command with the ! prefix, including ~/.local/bin, Flatpak exports, ~/go/bin, and "
            "home-relative names such as scripts/deploy. This is not a shell so pipes and redirection stay literal "
            "arguments. Prefix modes must stay enabled",
        )
        self._command_switch.set_sensitive(dependent_row_sensitive(self.settings.enable_prefix_modes))
        page.add(providers)

        extras = Adw.PreferencesGroup(title="Behavior")
        self._feature_switch(
            extras,
            "enable_prefix_modes",
            "Prefix modes",
            "= calculator, @ web, # settings, $ windows, . files, ! command. Use a space after # . and $ so "
            "#ff0000, .bashrc, and $HOME stay normal searches",
        )
        self._feature_switch(
            extras,
            "enable_empty_suggestions",
            "Empty-state suggestions",
            "Show windows and frequent apps before you type",
        )
        page.add(extras)

        desktop = Adw.PreferencesGroup(title="Desktop")
        recent_adjustment = Gtk.Adjustment(value=self.settings.max_recent_apps, lower=0, upper=20, step_increment=1)
        add_spin_row(
            desktop,
            "Number of frequent apps to show",
            "Pinned near the top of empty-state and app results.",
            recent_adjustment,
            self._on_recent_apps_changed,
        )
        raise_switch = add_switch_row(
            desktop,
            "Switch to application if already running",
            "Focus a running application instead of launching a duplicate. Works only on X11.",
            self.settings.raise_if_started,
            self._on_raise_toggled,
        )
        raise_switch.set_sensitive(IS_X11)
        add_switch_row(
            desktop,
            "Include foreign desktop apps",
            "Show applications hidden for your desktop environment by ignoring desktop filters.",
            self.settings.disable_desktop_filters,
            self._on_filters_toggled,
        )
        layer_switch = add_switch_row(
            desktop,
            "Enable Layer Shell",
            "Position on Wayland with Layer Shell when the compositor supports it.",
            self.settings.layer_shell,
            self._on_layer_toggled,
        )
        layer_switch.set_sensitive(not IS_X11)
        add_entry_row(
            desktop,
            "Terminal command",
            "Override the terminal binary for desktop entries that request a terminal. Leave blank for the default.",
            self.settings.terminal_command,
            self._on_terminal_changed,
        )
        page.add(desktop)
        return page

    def _build_web_search_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Web Search", icon_name="web-browser-symbolic")
        group = Adw.PreferencesGroup(
            title="Web Search",
            description=(
                "Web search appears when nothing else matches, or immediately with the @ prefix. "
                f"{engine_prefs_search_text()}."
            ),
        )
        self._feature_switch(
            group,
            "show_web_search",
            "Show web search fallback",
            "When nothing local matches. The @ prefix still searches the web",
        )
        self._engine_combo = add_combo_row(group, "Search engine", "", SEARCH_ENGINES, self.settings.web_search_engine)
        page.add(group)
        return page

    def _build_about_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="About", icon_name="dialog-information-symbolic")
        group = Adw.PreferencesGroup(title="About")
        group.add(plain_action_row("GoshLauncher", "A compact GTK4/Adwaita launcher with interchangeable looks."))
        group.add(plain_action_row("Looks", look_about_subtitle()))
        group.add(
            plain_action_row(
                "Toolkit",
                "GTK 4 and libadwaita 1.1+ (Ubuntu 22.04). Looks follow Spotlight-goshos.",
            )
        )
        about_version = f"{version} (Extension API v{api_version})"
        group.add(plain_action_row("Version", about_version))
        page.add(group)
        return page

    def _bind_settings_follow(self) -> None:
        self._prefs_signals = JsonSettingsSignals(self.settings)
        bind_settings_changed(self._prefs_signals, "look_id", self._look_combo, self._follow_look_combo)
        bind_settings_combo(self._position_combo, self._prefs_signals, "popup_position", list(POSITION_ITEMS))
        bind_settings_combo(self._density_combo, self._prefs_signals, "row_density", list(DENSITY_ITEMS))
        bind_settings_combo(self._order_combo, self._prefs_signals, "result_order", list(ORDER_ITEMS))
        bind_settings_combo(self._engine_combo, self._prefs_signals, "web_search_engine", SEARCH_ENGINES)
        bind_settings_changed(
            self._prefs_signals, "enable_application_mode", self._app_actions_switch, self._sync_dependent_switches
        )
        bind_settings_changed(
            self._prefs_signals, "enable_prefix_modes", self._command_switch, self._sync_dependent_switches
        )
        for attr, switch in self._chrome_switches.items():
            bind_settings_changed(self._prefs_signals, attr, switch, self._sync_chrome_widgets)
        for attr, spin in (
            ("base_width", self._width_spin),
            ("results_max_height", self._height_spin),
            ("max_per_category", self._max_spin),
            ("icon_size", self._icon_spin),
        ):
            bind_settings_changed(self._prefs_signals, attr, spin, self._sync_chrome_widgets)
        for attr, switch in self._feature_switches.items():
            bind_settings_changed(self._prefs_signals, attr, switch, self._sync_feature_switches)
        bind_settings_changed(self._prefs_signals, "hotkey_show_app", self._hotkey_label, self._refresh_hotkey_label)

    def _follow_look_combo(self) -> None:
        self._updating_chrome = True
        try:
            self._select_combo(self._look_combo, LOOKS, self.settings.look_id)
            look = next((item for item in LOOKS if item["id"] == self.settings.look_id), LOOKS[0])
            self._look_combo.set_subtitle(look["description"])
        finally:
            self._updating_chrome = False
        self._sync_chrome_widgets()

    def _sync_chrome_widgets(self) -> None:
        self._updating_chrome = True
        try:
            self._select_combo(self._position_combo, list(POSITION_ITEMS), self.settings.popup_position)
            self._select_combo(self._density_combo, list(DENSITY_ITEMS), self.settings.row_density)
            self._select_combo(self._order_combo, list(ORDER_ITEMS), self.settings.result_order)
            from ulauncher.modes.launcher.chrome_size import clamp_popup_width

            self._height_spin.set_value(self.settings.results_max_height)
            self._max_spin.set_value(self.settings.max_per_category)
            self._icon_spin.set_value(self.settings.icon_size)
            self._width_spin.set_value(clamp_popup_width(self.settings.base_width))
            for attr, switch in self._chrome_switches.items():
                desired = bool(getattr(self.settings, attr))
                if switch.get_active() != desired:
                    switch.set_active(desired)
        finally:
            self._updating_chrome = False

    def _sync_dependent_switches(self) -> None:
        self._app_actions_switch.set_sensitive(dependent_row_sensitive(self.settings.enable_application_mode))
        self._command_switch.set_sensitive(dependent_row_sensitive(self.settings.enable_prefix_modes))

    def _sync_feature_switches(self) -> None:
        self._updating_chrome = True
        try:
            for attr, switch in self._feature_switches.items():
                desired = bool(getattr(self.settings, attr))
                if switch.get_active() != desired:
                    switch.set_active(desired)
        finally:
            self._updating_chrome = False
        self._sync_dependent_switches()

    def _on_look_selected(self, combo: Adw.ComboRow, *_args: Any) -> None:
        if self._updating_chrome:
            return
        index = int(combo.get_selected())
        if index < 0 or index >= len(LOOKS):
            return
        look = LOOKS[index]
        combo.set_subtitle(look["description"])
        from ulauncher.modes.launcher.looks import apply_look_chrome, should_apply_look

        if not should_apply_look(self.settings.look_id, look["id"]):
            return
        apply_look_chrome(self.settings, look["id"])
        self._sync_chrome_widgets()

    def _on_reset_look_clicked(self, _: Gtk.Button) -> None:
        from ulauncher.modes.launcher.looks import apply_look_chrome

        apply_look_chrome(self.settings, self.settings.look_id)
        self._sync_chrome_widgets()

    def _on_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_chrome:
            return
        from ulauncher.modes.launcher.chrome_size import POPUP_WIDTH_MAX, POPUP_WIDTH_MIN

        width = spin.get_value_as_int()
        if POPUP_WIDTH_MIN <= width <= POPUP_WIDTH_MAX:
            self.settings.save({"base_width": width})

    def _on_screen_changed(self, combo: Adw.ComboRow, *_args: Any) -> None:
        if self._updating_chrome:
            return
        index = int(combo.get_selected())
        items = self._screen_items
        if 0 <= index < len(items):
            self.settings.save({"render_on_screen": items[index]["id"]})

    def _on_autostart_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        if is_enabled == self.autostart_pref.status().is_enabled:
            return
        try:
            self.autostart_pref.toggle(is_enabled)
        except OSError:
            logger.exception("Failed to toggle autostart")
            switch.set_active(not is_enabled)
            return
        self._tray_switch.set_sensitive(is_enabled)
        events.emit("app:toggle_hold", is_enabled)

    def _on_keep_alive_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        self.settings.save({"keep_alive": is_enabled})
        self._tray_switch.set_sensitive(is_enabled)
        events.emit("app:toggle_hold", is_enabled)

    def _on_tray_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        self.settings.save({"show_tray_icon": is_enabled})
        events.emit("app:toggle_tray_icon", is_enabled)

    def _on_auto_resume_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        if self._updating_chrome:
            return
        self.settings.save({"auto_resume": switch.get_active()})

    def _on_close_focus_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        if self._updating_chrome:
            return
        self.settings.save({"close_on_focus_out": switch.get_active()})

    def _on_grab_mouse_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        if self._updating_chrome:
            return
        self.settings.save({"grab_mouse_pointer": switch.get_active()})

    def _on_raise_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"raise_if_started": switch.get_active()})

    def _on_filters_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"disable_desktop_filters": switch.get_active()})

    def _on_layer_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"layer_shell": switch.get_active()})

    def _on_recent_apps_changed(self, spin: Gtk.SpinButton) -> None:
        self.settings.save({"max_recent_apps": spin.get_value_as_int()})

    def _on_terminal_changed(self, entry: Gtk.Entry) -> None:
        self.settings.save({"terminal_command": entry.get_text()})

    def _on_hotkey_clicked(self, _: Gtk.Button) -> None:
        HotkeyController.show_dialog()

    def _refresh_hotkey_label(self) -> None:
        from ulauncher.modes.launcher.shortcut import shortcut_row_label

        accel = HotkeyController.current_accelerator()
        self._hotkey_label.set_text(shortcut_row_label([accel] if accel else [], self._hotkey_capturing))

    def _on_hotkey_capture_activate(self) -> None:
        from ulauncher.modes.launcher.shortcut import next_shortcut_capture_action

        if next_shortcut_capture_action(self._hotkey_capturing, "activate") != "start":
            return
        self._hotkey_capturing = True
        self._refresh_hotkey_label()
        self._shortcut_row.grab_focus()

    def _on_hotkey_focus(self, row: Adw.ActionRow, *_args: Any) -> None:
        from ulauncher.modes.launcher.shortcut import next_shortcut_capture_action

        if row.has_focus() or not self._hotkey_capturing:
            return
        if next_shortcut_capture_action(self._hotkey_capturing, "focus-out") != "cancel":
            return
        self._hotkey_capturing = False
        self._refresh_hotkey_label()

    def _on_hotkey_capture_key(self, _controller: Any, keyval: int, _keycode: int, state: int) -> bool:
        from ulauncher.modes.launcher.shortcut import (
            build_accelerator,
            modifiers_from_mask,
            next_shortcut_capture_action,
            shortcut_capture_key_kind,
        )

        kind = shortcut_capture_key_kind(Gdk.keyval_name(keyval))
        action = next_shortcut_capture_action(self._hotkey_capturing, kind)
        if action == "ignore":
            return False
        if action == "cancel":
            self._hotkey_capturing = False
            self._refresh_hotkey_label()
            return True
        if action != "commit":
            return True
        key_name = Gdk.keyval_name(keyval) or ""
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
        accel = build_accelerator(key_name, mods)
        if not accel:
            return True
        self._hotkey_capturing = False
        HotkeyController.apply_accelerator(accel)
        self._refresh_hotkey_label()
        return True

    def _on_hotkey_reset_clicked(self, _: Gtk.Button) -> None:
        from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK

        self._hotkey_capturing = False
        HotkeyController.apply_accelerator(DEFAULT_FALLBACK)
        self._refresh_hotkey_label()
