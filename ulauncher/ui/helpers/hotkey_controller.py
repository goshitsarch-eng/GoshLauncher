from __future__ import annotations

import logging
import subprocess
from shutil import which
from typing import Any, Callable

from ulauncher import app_id
from ulauncher.gi import Gio, GLib
from ulauncher.modes.launcher.shortcut import (
    hotkey_to_restore_after_failed_grab,
    shortcut_attempts,
    shortcut_retry_list,
)
from ulauncher.ui.hotkey_dialog import HotkeyDialog
from ulauncher.utils.environment import DESKTOP_ID, DESKTOP_NAME
from ulauncher.utils.launch_detached import launch_detached
from ulauncher.utils.systemd_controller import SystemdController

logger = logging.getLogger(__name__)
launch_command = f"gapplication launch {app_id}"


IS_SUPPORTED = DESKTOP_ID in ("GNOME", "XFCE", "PLASMA")


def _set_hotkey(hotkey: str) -> None:
    if not hotkey:
        return

    if DESKTOP_ID == "GNOME":
        base_schema = "org.gnome.settings-daemon.plugins.media-keys"
        spec_schema = f"{base_schema}.custom-keybinding"
        spec_path = f"/{spec_schema.replace('.', '/')}s/ulauncher/"

        spec = Gio.Settings.new_with_path(spec_schema, spec_path)
        spec.set_string("name", "Show Ulauncher")
        spec.set_string("command", launch_command)
        spec.set_string("binding", hotkey)

        keybindings = Gio.Settings.new(base_schema)
        enabled_keybindings = list(keybindings.get_value("custom-keybindings"))  # type: ignore[call-overload]
        if spec_path not in enabled_keybindings:
            logger.debug("Enabling global shortcut for Gnome")
            enabled_keybindings.append(spec_path)

        logger.debug("Saving global shortcut '%s' for Gnome", hotkey)
        keybindings.set_value("custom-keybindings", GLib.Variant("as", enabled_keybindings))
    elif DESKTOP_ID == "XFCE":
        cmd_prefix = ["xfconf-query", "--channel", "xfce4-keyboard-shortcuts"]
        all_shortcuts = subprocess.check_output([*cmd_prefix, "--list", "--verbose"]).decode().strip().split("\n")
        # Unset existing bindings
        for shortcut in all_shortcuts:
            if shortcut.endswith(launch_command):
                prop = shortcut.split()[0]
                subprocess.run([*cmd_prefix, "--reset", "--property", prop], check=True)

        cmd = [
            *cmd_prefix,
            "--property",
            f"/commands/custom/{hotkey}",
            "--create",
            "--type",
            "string",
            "--set",
            launch_command,
        ]
        logger.debug("Executing command to add XFCE global shortcut: %s", " ".join(cmd))
        subprocess.run(cmd, check=True)
    else:
        logger.warning("Ulauncher doesn't support setting hotkey for Desktop environment '%s'", DESKTOP_NAME)


class HotkeyController:
    _portal_session: Any = None

    @staticmethod
    def is_supported() -> bool:
        return IS_SUPPORTED

    @staticmethod
    def is_plasma() -> bool:
        return DESKTOP_ID == "PLASMA"

    @staticmethod
    def show_dialog() -> None:
        if DESKTOP_ID == "PLASMA":
            # I haven't found the specifics in why the systemsettings command was renamed
            # and if we have to support more than these, but at least systemsettings5 is the old one
            for syssettings_alias in ("systemsettings", "systemsettings5"):
                if which(syssettings_alias):
                    launch_detached([syssettings_alias, "kcm_keys"])
                    return

        elif IS_SUPPORTED:
            previous = _current_gnome_grab() if DESKTOP_ID == "GNOME" else ""
            requested = HotkeyDialog().run()
            if not requested:
                return
            try:
                _set_hotkey(requested)
            except (GLib.GError, OSError, subprocess.CalledProcessError, TypeError, ValueError):
                logger.debug("Shortcut grab failed for %s", requested, exc_info=True)
                restore = hotkey_to_restore_after_failed_grab(False, previous)
                if restore:
                    try:
                        _set_hotkey(restore)
                    except (GLib.GError, OSError, subprocess.CalledProcessError, TypeError, ValueError):
                        logger.debug("Could not restore previous shortcut grab", exc_info=True)

    @staticmethod
    def setup_default(default_hotkey: str) -> bool:
        if DESKTOP_ID == "PLASMA":
            hotkey = "Ctrl+Space"
            config_path = ["--file", "kglobalshortcutsrc", "--group", f"{app_id}.desktop", "--key"]
            config = subprocess.check_output(["kreadconfig5", *config_path, '"_launch"'])
            # only proceed if it's not already set up (don't override user prefs)
            if config.decode().strip():
                logger.debug("Ulauncher Plasma global shortcut already created")
                return False
            if default_hotkey not in {"<Primary>space", "<Control>space"}:
                # We don't want to convert the hotkey, so instead we just hard code it
                logger.warning("Ignoring hotkey argument %s and using default '%s'", default_hotkey, hotkey)
            logger.debug("Executing kwriteconfig5 commands to add Plasma global shortcut for '%s'", hotkey)
            subprocess.run(["kwriteconfig5", *config_path, "_k_friendly_name", "Ulauncher"], check=True)
            subprocess.run(["kwriteconfig5", *config_path, "_launch", f"{hotkey},none,Ulauncher"], check=True)
            plasma_service_controller = SystemdController("plasma-kglobalaccel")
            if plasma_service_controller.status().can_start:
                plasma_service_controller.restart()
            return True
        if IS_SUPPORTED:
            current = _current_gnome_grab() if DESKTOP_ID == "GNOME" else ""
            if current and not shortcut_retry_list(default_hotkey, current):
                logger.debug("Keeping previous global shortcut grab")
                return False
            for accel in shortcut_attempts(default_hotkey):
                try:
                    _set_hotkey(accel)
                except (GLib.GError, OSError, subprocess.CalledProcessError, TypeError, ValueError):
                    logger.debug("Shortcut grab failed for %s", accel, exc_info=True)
                else:
                    return True
            return False
        return False

    @staticmethod
    def bind_session_hotkey(hotkey: str, on_toggle: Callable[[], None]) -> Any:
        """Bind Ctrl+Space via the GlobalShortcuts portal on compositors without a DE store.

        GNOME/XFCE/Plasma already persist a custom keybinding. Re-binding those
        through the portal would show a second permission dialog and toggle twice.
        """
        from ulauncher.modes.launcher.global_shortcuts import GlobalShortcutsPortal, should_bind_portal

        if not should_bind_portal(DESKTOP_ID):
            return None
        portal = GlobalShortcutsPortal(on_toggle)
        if not portal.start(hotkey, app_id):
            return None
        HotkeyController._portal_session = portal
        return portal


def _current_gnome_grab() -> str:
    try:
        base_schema = "org.gnome.settings-daemon.plugins.media-keys"
        spec_schema = f"{base_schema}.custom-keybinding"
        spec_path = f"/{spec_schema.replace('.', '/')}s/ulauncher/"
        spec = Gio.Settings.new_with_path(spec_schema, spec_path)
        return spec.get_string("binding") or ""
    except (GLib.GError, AttributeError, TypeError):
        return ""
