from __future__ import annotations

import logging
from typing import Any

from gi.repository import Gtk

from ulauncher.ui.helpers.hotkey_controller import HotkeyController
from ulauncher.ui.helpers.theme import get_themes
from ulauncher.ui.preferences.views import BaseView, styled
from ulauncher.utils.environment import IS_X11
from ulauncher.utils.eventbus import EventBus
from ulauncher.utils.settings import Settings
from ulauncher.utils.systemd_controller import SystemdController

logger = logging.getLogger(__name__)
events = EventBus()


class PreferencesView(BaseView):
    """General preferences page"""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.settings: Settings = Settings.load()
        self.autostart_pref: SystemdController = SystemdController("ulauncher")

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_propagate_natural_width(True)
        scrolled.set_propagate_natural_height(True)
        self.pack_start(scrolled, True, True, 0)

        # Create main container - centers on wide screens, fills on narrow screens
        prefs_view = styled(
            Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                margin_top=30,
                margin_bottom=30,
                margin_start=30,
                margin_end=30,
                spacing=24,
            ),
            "preferences-content",
        )
        prefs_view.set_halign(Gtk.Align.CENTER)
        prefs_view.set_valign(Gtk.Align.START)
        prefs_view.set_size_request(600, -1)  # min-width of 600px
        scrolled.add(prefs_view)

        # Add sections
        self._updating_chrome = False
        self._add_general_section(prefs_view)
        self._add_chrome_section(prefs_view)
        self._add_applications_section(prefs_view)
        self._add_launcher_section(prefs_view)
        self._add_advanced_section(prefs_view)

    def _add_section_header(self, parent: Gtk.Box, title: str) -> None:
        """Add a section header"""
        label = Gtk.Label(
            label=title,
            halign=Gtk.Align.START,
            margin_top=10,
            margin_bottom=2,
        )
        styled(label, "preferences-section-title")
        parent.pack_start(label, False, False, 0)

    def _create_section_container(self, parent: Gtk.Box, title: str) -> Gtk.Box:
        """Create a stylized section card"""
        self._add_section_header(parent, title)
        section_box = styled(
            Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, margin_top=0),
            "preferences-section-card",
        )
        parent.pack_start(section_box, False, False, 0)
        return section_box

    def _add_setting_row(
        self,
        parent: Gtk.Box,
        label_text: str,
        widget: Gtk.Widget,
        description: str,
        full_width: bool = False,
        is_warning: bool = False,
    ) -> None:
        """Add a settings row with label and widget

        Args:
            parent: The parent container
            label_text: The setting label
            widget: The control widget
            description: Description text
            full_width: If True, widget takes full width below label (for long inputs like Entry)
            is_warning: If True, style the description as a warning using GTK's 'warning' class
        """
        row_box = styled(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24), "preferences-setting-row")
        row_box.set_hexpand(True)

        # Left side - label and description
        label_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        if not full_width:
            label_container.set_hexpand(True)
        else:
            label_container.set_size_request(360, -1)

        label = styled(Gtk.Label(label=label_text, halign=Gtk.Align.START), "preferences-setting-title")
        label.set_xalign(0.0)
        label_container.pack_start(label, False, False, 0)

        desc_label = styled(
            Gtk.Label(
                label=description,
                halign=Gtk.Align.START,
                wrap=True,
                max_width_chars=70,
                margin_top=2,
                use_markup=True,
            ),
            "preferences-setting-description",
        )
        desc_label.set_xalign(0.0)
        if is_warning:
            desc_label.get_style_context().add_class("warning-label")
        label_container.pack_start(desc_label, False, False, 0)

        if full_width:
            # For long inputs: stack vertically
            container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            container.pack_start(label_container, False, False, 0)
            widget.set_halign(Gtk.Align.FILL)
            widget.set_hexpand(True)
            container.pack_start(widget, False, False, 0)
            row_box.pack_start(container, True, True, 0)
        else:
            # For buttons/switches/combos: place on right side
            row_box.pack_start(label_container, True, True, 0)
            widget.set_halign(Gtk.Align.END)
            widget.set_valign(Gtk.Align.START)
            row_box.pack_start(widget, False, False, 0)

        parent.pack_start(row_box, False, False, 0)

    def _add_general_section(self, parent: Gtk.Box) -> None:
        """Add general settings section"""
        general_box = self._create_section_container(parent, "General")
        run_in_bg_footer = "\n<b>Recommended:</b> Enabling this will make Ulauncher open noticeably faster."

        # Run in background (via systemd autostart, or keep-alive fallback)
        autostart_status = self.autostart_pref.status()
        if autostart_status.can_start:
            autostart_switch = Gtk.Switch(active=autostart_status.is_enabled)
            autostart_switch.connect("notify::active", self._on_autostart_toggled)
            desc = "Start Ulauncher automatically with your desktop session so it's ready when you need it."
            self._add_setting_row(general_box, "Run in background", autostart_switch, f"{desc}{run_in_bg_footer}")
        else:
            keep_alive_switch = Gtk.Switch(active=self.settings.keep_alive)
            keep_alive_switch.connect("notify::active", self._on_keep_alive_toggled)
            desc = "Keep Ulauncher running in the background after first use so it stays ready"
            self._add_setting_row(general_box, "Run in background", keep_alive_switch, f"{desc}{run_in_bg_footer}")

        self._add_tray_icon_row(general_box)

        # Hotkey
        if HotkeyController.is_supported():
            hotkey_button = Gtk.Button.new_with_label("Set hotkey")
            hotkey_button.connect("clicked", self._on_hotkey_clicked)
            hotkey_desc = "Choose the global keyboard shortcut that opens Ulauncher."
            self._add_setting_row(general_box, "Hotkey", hotkey_button, hotkey_desc)
        else:
            warning_text = (
                "Ulauncher doesn't support setting global shortcuts for your desktop environment. "
                "Bind this command in your DE settings: gapplication launch io.ulauncher.Ulauncher"
            )
            unavailable_label = Gtk.Label(label="Not available", sensitive=False)
            self._add_setting_row(general_box, "Hotkey", unavailable_label, warning_text, is_warning=True)

        # Color theme
        theme_combo = Gtk.ComboBoxText()
        themes = get_themes()
        for theme in themes:
            theme_combo.append(theme, theme)
        theme_combo.set_active_id(self.settings.theme_name)
        theme_combo.connect("changed", self._on_theme_changed)
        theme_desc = "Switch between installed themes. Changes apply immediately when you relaunch the UI."
        self._add_setting_row(general_box, "Color theme", theme_combo, theme_desc)

        look_combo = Gtk.ComboBoxText()
        from ulauncher.modes.launcher.looks import LOOKS

        for look in LOOKS:
            look_combo.append(look["id"], look["title"])
        look_combo.set_active_id(getattr(self.settings, "look_id", "spotlight"))
        look_combo.connect("changed", self._on_look_changed)
        look_desc = (
            "Launcher chrome (position, density, headers, number hints, icons). "
            "Width is separate. Matches Spotlight-goshos looks."
        )
        self._add_setting_row(general_box, "Launcher look", look_combo, look_desc)

        # Screen to show on
        screen_combo = Gtk.ComboBoxText()
        screen_combo.append("mouse-pointer-monitor", "The screen with the mouse pointer")
        screen_combo.append("default-monitor", "The default screen")
        screen_combo.set_active_id(self.settings.render_on_screen)
        screen_combo.connect("changed", self._on_screen_changed)
        screen_desc = "Decide which monitor presents Ulauncher when you press the hotkey."
        self._add_setting_row(general_box, "Screen to show on", screen_combo, screen_desc)

        # Auto resume
        auto_resume_switch = Gtk.Switch(active=self.settings.auto_resume)
        auto_resume_switch.connect("notify::active", self._on_auto_resume_toggled)
        auto_resume_desc = "If you close Ulauncher without running the query, restore it on the next session."
        self._add_setting_row(general_box, "Auto-resume unfinished sessions", auto_resume_switch, auto_resume_desc)

        # Close on focus out
        close_focus_switch = Gtk.Switch(active=self.settings.close_on_focus_out)
        close_focus_switch.connect("notify::active", self._on_close_focus_toggled)
        focus_desc = "Hide the Ulauncher window automatically as soon as another app grabs focus."
        self._add_setting_row(general_box, "Close Ulauncher when losing focus", close_focus_switch, focus_desc)

        # Grab mouse pointer
        grab_mouse_switch = Gtk.Switch(active=self.settings.grab_mouse_pointer)
        grab_mouse_switch.connect("notify::active", self._on_grab_mouse_toggled)
        grab_desc = "Capture the pointer to prevent focus-follows-mouse setups from stealing the launcher focus."
        self._add_setting_row(general_box, "Grab mouse pointer focus", grab_mouse_switch, grab_desc)

    def _add_chrome_section(self, parent: Gtk.Box) -> None:
        """Look chrome overrides from spotlight-goshos appearance page."""
        chrome_box = self._create_section_container(parent, "Launcher chrome")

        position_combo = Gtk.ComboBoxText()
        position_combo.append("center", "Center")
        position_combo.append("top", "Top")
        position_combo.set_active_id(self.settings.popup_position)
        position_combo.connect("changed", self._on_chrome_combo("popup_position"))
        self._position_combo = position_combo
        self._add_setting_row(
            chrome_box,
            "Position",
            position_combo,
            "Center stays put and grows down. Top matches Pop!_OS and KRunner.",
        )

        density_combo = Gtk.ComboBoxText()
        density_combo.append("comfortable", "Comfortable")
        density_combo.append("compact", "Compact")
        density_combo.set_active_id(self.settings.row_density)
        density_combo.connect("changed", self._on_chrome_combo("row_density"))
        self._density_combo = density_combo
        self._add_setting_row(chrome_box, "Row density", density_combo, "Compact still shrinks the look's icon size.")

        height_adjust = Gtk.Adjustment(
            value=self.settings.results_max_height, lower=160, upper=800, step_increment=20
        )
        height_spin = Gtk.SpinButton(adjustment=height_adjust)
        height_spin.connect("value-changed", self._on_int_setting("results_max_height"))
        self._height_spin = height_spin
        self._add_setting_row(chrome_box, "Results max height", height_spin, "Scroll after this height.")

        max_adjust = Gtk.Adjustment(value=self.settings.max_per_category, lower=1, upper=20, step_increment=1)
        max_spin = Gtk.SpinButton(adjustment=max_adjust)
        max_spin.connect("value-changed", self._on_int_setting("max_per_category"))
        self._max_spin = max_spin
        self._add_setting_row(chrome_box, "Max results per category", max_spin, "Cap for each provider group.")

        icon_adjust = Gtk.Adjustment(value=self.settings.icon_size, lower=16, upper=64, step_increment=2)
        icon_spin = Gtk.SpinButton(adjustment=icon_adjust)
        icon_spin.connect("value-changed", self._on_int_setting("icon_size"))
        self._icon_spin = icon_spin
        self._add_setting_row(chrome_box, "Result icon size", icon_spin, "Pixels. Compact density still shrinks this.")

        self._chrome_switches: dict[str, Gtk.Switch] = {}
        for attr, title, description in (
            ("show_search_icon", "Search icon", "Magnifying glass in the entry."),
            ("show_section_headers", "Section headers", "Category labels above result groups."),
            ("show_result_icons", "Result icons", "Show icons on result rows."),
            ("show_descriptions", "Result descriptions", "Show the second line on result rows."),
            ("show_result_numbers", "Number hints", "Show 1-9 and activate with Alt+digit."),
        ):
            switch = Gtk.Switch(active=bool(getattr(self.settings, attr)))
            switch.connect("notify::active", self._on_bool_setting(attr))
            self._chrome_switches[attr] = switch
            self._add_setting_row(chrome_box, title, switch, description)

        reset_btn = Gtk.Button(label="Reset")
        reset_btn.connect("clicked", self._on_reset_look_clicked)
        self._add_setting_row(
            chrome_box,
            "Reset look",
            reset_btn,
            "Restore this look's position, density, headers, icons, descriptions, number hints, icon size, and order.",
        )

    def _on_chrome_combo(self, attr: str) -> Any:
        def on_changed(combo: Gtk.ComboBoxText) -> None:
            if self._updating_chrome:
                return
            value = combo.get_active_id()
            if value:
                self.settings.save({attr: value})

        return on_changed

    def _on_int_setting(self, attr: str) -> Any:
        def on_changed(spin: Gtk.SpinButton) -> None:
            if self._updating_chrome:
                return
            self.settings.save({attr: spin.get_value_as_int()})

        return on_changed

    def _on_reset_look_clicked(self, _: Gtk.Button) -> None:
        from ulauncher.modes.launcher.looks import apply_look_chrome

        apply_look_chrome(self.settings, self.settings.look_id)
        self._sync_chrome_widgets()

    def _sync_chrome_widgets(self) -> None:
        self._updating_chrome = True
        try:
            if hasattr(self, "_position_combo"):
                self._position_combo.set_active_id(self.settings.popup_position)
            if hasattr(self, "_density_combo"):
                self._density_combo.set_active_id(self.settings.row_density)
            if hasattr(self, "_order_combo"):
                self._order_combo.set_active_id(self.settings.result_order)
            if hasattr(self, "_height_spin"):
                self._height_spin.set_value(self.settings.results_max_height)
            if hasattr(self, "_max_spin"):
                self._max_spin.set_value(self.settings.max_per_category)
            if hasattr(self, "_icon_spin"):
                self._icon_spin.set_value(self.settings.icon_size)
            for attr, switch in getattr(self, "_chrome_switches", {}).items():
                switch.set_active(bool(getattr(self.settings, attr)))
        finally:
            self._updating_chrome = False

    def _add_applications_section(self, parent: Gtk.Box) -> None:
        """Add applications settings section"""
        applications_box = self._create_section_container(parent, "Applications")

        # Enable application mode
        app_mode_switch = Gtk.Switch(active=self.settings.enable_application_mode)
        app_mode_switch.connect("notify::active", self._on_app_mode_toggled)
        desc = "Include desktop applications alongside shortcuts and extensions in search results."
        self._add_setting_row(applications_box, "Include applications in search", app_mode_switch, desc)

        # Raise if started
        raise_switch = Gtk.Switch(active=self.settings.raise_if_started, sensitive=IS_X11)
        raise_switch.connect("notify::active", self._on_raise_toggled)
        desc = "Focus an already running application instead of launching a duplicate instance. Works only on X11."

        self._add_setting_row(applications_box, "Switch to application if already running", raise_switch, desc)

        # Window width
        width_adjustment = Gtk.Adjustment(value=self.settings.base_width, lower=540, upper=2000, step_increment=10)
        width_spin = Gtk.SpinButton(adjustment=width_adjustment)
        width_spin.connect("value-changed", self._on_width_changed)
        desc = "Set the launcher width between 540 and 2000 pixels to match your workspace."
        self._add_setting_row(applications_box, "Window width", width_spin, desc)

        # Top apps
        recent_adjustment = Gtk.Adjustment(value=self.settings.max_recent_apps, lower=0, upper=20, step_increment=1)
        recent_spin = Gtk.SpinButton(adjustment=recent_adjustment)
        recent_spin.connect("value-changed", self._on_recent_apps_changed)
        desc = "Control how many frequently used applications remain pinned near the top of the results."
        self._add_setting_row(applications_box, "Number of frequent apps to show", recent_spin, desc)

    def _add_launcher_section(self, parent: Gtk.Box) -> None:
        """Spotlight-goshos provider toggles, prefixes, web engine, and empty-state."""
        launcher_box = self._create_section_container(parent, "Launcher features")

        prefix_switch = Gtk.Switch(active=self.settings.enable_prefix_modes)
        prefix_switch.connect("notify::active", self._on_prefix_modes_toggled)
        self._add_setting_row(
            launcher_box,
            "Prefix modes",
            prefix_switch,
            "Jump to one provider with = calc, @ web, # settings, $ windows, . recents, ! command. "
            "#ff0000, $HOME, and .bashrc stay normal queries.",
        )

        empty_switch = Gtk.Switch(active=self.settings.enable_empty_suggestions)
        empty_switch.connect("notify::active", self._on_bool_setting("enable_empty_suggestions"))
        self._add_setting_row(
            launcher_box,
            "Empty-state suggestions",
            empty_switch,
            "When the query is empty, show frequent apps and open windows (windows first for Pop!_OS look).",
        )

        app_actions_switch = Gtk.Switch(active=self.settings.enable_app_actions)
        app_actions_switch.connect("notify::active", self._on_bool_setting("enable_app_actions"))
        self._add_setting_row(
            launcher_box,
            "Application actions",
            app_actions_switch,
            "Offer desktop-file actions such as New Window alongside the main launch row.",
        )

        for attr, title, description in (
            (
                "enable_url_open",
                "Open URLs",
                "Detect domains, IPs, and schemes such as https, sftp, mailto, and magnet.",
            ),
            (
                "enable_path_open",
                "Open paths",
                "Open ~/…, ./…, and absolute filesystem paths, including Open in Terminal.",
            ),
            ("enable_places", "XDG folders", "Match Home, Documents, Downloads, and the other user directories."),
            ("enable_bookmarks", "GTK bookmarks", "Search ~/.config/gtk-3.0/bookmarks and gtk-4.0/bookmarks."),
            ("enable_calculator", "Calculator", "Recursive-descent math. Bare 42 is not math unless you type =42."),
            (
                "enable_unit_convert",
                "Unit conversion",
                "Convert length, mass, temperature, data size, and related units.",
            ),
            ("enable_color_hex", "Colors", "Copy hex, rgb, hsl, hwb, and CSS color names."),
            ("enable_time_date", "Clock", "Copy the local time or date for queries such as time, now, or tomorrow."),
            ("enable_window_search", "Windows", "Switch, close, or kill open windows, including workspace N."),
            ("enable_system_actions", "System actions", "Lock, suspend, restart, power off, log out, and screenshots."),
            ("enable_settings_search", "Settings panels", "Open GNOME Settings panels such as Wi-Fi or Displays."),
            ("enable_recent_files", "Recent files", "Search recently-used.xbel entries."),
            (
                "show_web_search",
                "Web search fallback",
                "Offer a web search when nothing local matches. @ still searches.",
            ),
        ):
            switch = Gtk.Switch(active=bool(getattr(self.settings, attr)))
            switch.connect("notify::active", self._on_bool_setting(attr))
            self._add_setting_row(launcher_box, title, switch, description)

        self._command_switch = Gtk.Switch(
            active=self.settings.enable_command_run, sensitive=self.settings.enable_prefix_modes
        )
        self._command_switch.connect("notify::active", self._on_bool_setting("enable_command_run"))
        self._add_setting_row(
            launcher_box,
            "Command runner",
            self._command_switch,
            "Run argv with the ! prefix. Off by default. Insensitive while prefix modes are off.",
        )

        engine_combo = Gtk.ComboBoxText()
        from ulauncher.modes.launcher.web import SEARCH_ENGINES

        for engine in SEARCH_ENGINES:
            engine_combo.append(engine["id"], engine["label"])
        engine_combo.set_active_id(self.settings.web_search_engine)
        engine_combo.connect("changed", self._on_web_engine_changed)
        self._add_setting_row(
            launcher_box,
            "Web search engine",
            engine_combo,
            "Engine used for @ queries and the web fallback.",
        )

        order_combo = Gtk.ComboBoxText()
        order_combo.append("default", "Apps first")
        order_combo.append("windows-first", "Windows first (Pop!_OS)")
        order_combo.set_active_id(self.settings.result_order)
        order_combo.connect("changed", self._on_result_order_changed)
        self._order_combo = order_combo
        self._add_setting_row(
            launcher_box,
            "Result order",
            order_combo,
            "Pop!_OS look also forces windows-first. Other looks keep apps first unless you override here.",
        )

    def _on_bool_setting(self, attr: str) -> Any:
        def on_toggle(switch: Gtk.Switch, _: Any) -> None:
            if self._updating_chrome:
                return
            self.settings.save({attr: switch.get_active()})

        return on_toggle

    def _on_prefix_modes_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        enabled = switch.get_active()
        self.settings.save({"enable_prefix_modes": enabled})
        if hasattr(self, "_command_switch"):
            self._command_switch.set_sensitive(enabled)

    def _on_web_engine_changed(self, combo: Gtk.ComboBoxText) -> None:
        engine_id = combo.get_active_id()
        if engine_id:
            self.settings.save({"web_search_engine": engine_id})

    def _on_result_order_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._updating_chrome:
            return
        order = combo.get_active_id()
        if order:
            self.settings.save({"result_order": order})

    def _add_advanced_section(self, parent: Gtk.Box) -> None:
        """Add advanced settings section"""
        advanced_box = self._create_section_container(parent, "Advanced")

        # Desktop filters
        filters_switch = Gtk.Switch(active=self.settings.disable_desktop_filters)
        filters_switch.connect("notify::active", self._on_filters_toggled)
        desc = "Show applications that are hidden for your desktop environment by ignoring desktop filters."
        self._add_setting_row(advanced_box, "Include foreign desktop apps", filters_switch, desc)

        # Window shadow
        shadow_adjustment = Gtk.Adjustment(value=self.settings.window_shadow, lower=0, upper=25, step_increment=1)
        shadow_spin = Gtk.SpinButton(adjustment=shadow_adjustment)
        shadow_spin.connect("value-changed", self._on_shadow_changed)
        desc = (
            "The window shadow size. Set to 0 to disable. "
            "Shadows are also disabled if we detect your window manager cannot support them."
        )
        self._add_setting_row(advanced_box, "Window shadow size", shadow_spin, desc)

        # GTK Layer Shell
        layer_switch = Gtk.Switch(active=self.settings.layer_shell, sensitive=not IS_X11)
        layer_switch.connect("notify::active", self._on_layer_toggled)
        desc = (
            "Use Layer Shell for positioning on Wayland (when supported). "
            "Recommended unless your desktop handles Wayland positioning separately (Hyprland)"
        )
        self._add_setting_row(advanced_box, "Enable Layer Shell", layer_switch, desc)

        # Jump keys
        jump_entry = Gtk.Entry(text=self.settings.jump_keys, width_chars=50)
        jump_entry.connect("changed", self._on_jump_keys_changed)
        desc = "Configure the characters used for jumping directly to a result with modifier shortcuts."
        self._add_setting_row(advanced_box, "Jump keys", jump_entry, desc, full_width=True)

        # Terminal command
        terminal_entry = Gtk.Entry(text=self.settings.terminal_command, width_chars=50)
        terminal_entry.connect("changed", self._on_terminal_changed)
        desc = (
            "Override the terminal binary for desktop entries that request a terminal. Leave blank to use the default."
        )
        self._add_setting_row(advanced_box, "Terminal command", terminal_entry, desc, full_width=True)

    def _add_tray_icon_row(self, parent: Gtk.Box) -> None:
        # Placed next to "Run in background" because the tray icon is only effective while persistent.
        self._tray_switch = Gtk.Switch(active=self.settings.show_tray_icon, sensitive=self.settings.is_persistent())
        self._tray_switch.connect("notify::active", self._on_tray_toggled)
        desc = (
            "Display a tray icon for quick actions. Only available while Ulauncher is set to "
            "run in the background. Also requires AppIndicator3 or XApp on X11."
        )
        self._add_setting_row(parent, "Show tray icon", self._tray_switch, desc)

    # Event handlers
    def _on_autostart_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        # Skip if already in sync - notably when set_active() below re-fires this handler.
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

    def _on_hotkey_clicked(self, _: Gtk.Button) -> None:
        HotkeyController.show_dialog()

    def _on_theme_changed(self, combo: Gtk.ComboBoxText) -> None:
        theme_name = combo.get_active_text()
        if theme_name:
            self.settings.save({"theme_name": theme_name})

    def _on_look_changed(self, combo: Gtk.ComboBoxText) -> None:
        look_id = combo.get_active_id()
        if look_id:
            from ulauncher.modes.launcher.looks import apply_look_chrome

            apply_look_chrome(self.settings, look_id)
            self._sync_chrome_widgets()

    def _on_screen_changed(self, combo: Gtk.ComboBoxText) -> None:
        screen = combo.get_active_id()
        if screen:
            self.settings.save({"render_on_screen": screen})

    def _on_auto_resume_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"auto_resume": switch.get_active()})

    def _on_close_focus_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"close_on_focus_out": switch.get_active()})

    def _on_grab_mouse_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"grab_mouse_pointer": switch.get_active()})

    def _on_app_mode_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"enable_application_mode": switch.get_active()})

    def _on_raise_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"raise_if_started": switch.get_active()})

    def _on_width_changed(self, spin: Gtk.SpinButton) -> None:
        min_width = 540
        max_width = 2000
        width = spin.get_value_as_int()
        if min_width <= width <= max_width:
            self.settings.save({"base_width": width})

    def _on_recent_apps_changed(self, spin: Gtk.SpinButton) -> None:
        count = spin.get_value_as_int()
        self.settings.save({"max_recent_apps": count})

    def _on_shadow_changed(self, spin: Gtk.SpinButton) -> None:
        self.settings.save({"window_shadow": spin.get_value_as_int()})

    def _on_layer_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"layer_shell": switch.get_active()})

    def _on_tray_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        self.settings.save({"show_tray_icon": is_enabled})
        events.emit("app:toggle_tray_icon", is_enabled)

    def _on_filters_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        self.settings.save({"disable_desktop_filters": switch.get_active()})

    def _on_keep_alive_toggled(self, switch: Gtk.Switch, _: Any) -> None:
        is_enabled = switch.get_active()
        self.settings.save({"keep_alive": is_enabled})
        self._tray_switch.set_sensitive(is_enabled)
        events.emit("app:toggle_hold", is_enabled)

    def _on_jump_keys_changed(self, entry: Gtk.Entry) -> None:
        self.settings.save({"jump_keys": entry.get_text()})

    def _on_terminal_changed(self, entry: Gtk.Entry) -> None:
        self.settings.save({"terminal_command": entry.get_text()})
