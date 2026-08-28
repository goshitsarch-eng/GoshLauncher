"""Global-shortcut management per desktop environment.

GNOME/XFCE store a custom keybinding in the DE's own settings (via the
``gsettings``/``xfconf-query`` CLIs - no GLib binding needed); Plasma gets a
kglobalshortcutsrc entry; everything else binds through the XDG GlobalShortcuts
portal each startup (portal sessions die with the process).
"""

from __future__ import annotations

import ast
import logging
import subprocess
from shutil import which
from typing import Any, Callable

from ulauncher import app_display_name, app_id, show_launcher_label
from ulauncher.modes.launcher.shortcut import (
    hotkey_to_restore_after_failed_grab,
    shortcut_attempts,
    shortcut_retry_list,
)
from ulauncher.utils.environment import DESKTOP_ID, DESKTOP_NAME
from ulauncher.utils.launch_detached import launch_detached

logger = logging.getLogger(__name__)
launch_command = "ulauncher toggle"

IS_SUPPORTED = DESKTOP_ID in ("GNOME", "XFCE", "PLASMA")

_GNOME_BASE_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
_GNOME_SPEC_SCHEMA = f"{_GNOME_BASE_SCHEMA}.custom-keybinding"
_GNOME_SPEC_PATH = f"/{_GNOME_SPEC_SCHEMA.replace('.', '/')}s/ulauncher/"


def _gsettings(*args: str) -> str:
    return subprocess.check_output(["gsettings", *args], text=True, timeout=5).strip()  # noqa: S603, S607


def _set_hotkey(hotkey: str) -> None:
    if not hotkey:
        return

    if DESKTOP_ID == "GNOME":
        spec = f"{_GNOME_SPEC_SCHEMA}:{_GNOME_SPEC_PATH}"
        _gsettings("set", spec, "name", show_launcher_label)
        _gsettings("set", spec, "command", launch_command)
        _gsettings("set", spec, "binding", hotkey)

        raw = _gsettings("get", _GNOME_BASE_SCHEMA, "custom-keybindings")
        try:
            enabled_keybindings = list(ast.literal_eval(raw.removeprefix("@as ")))
        except (ValueError, SyntaxError):
            enabled_keybindings = []
        if _GNOME_SPEC_PATH not in enabled_keybindings:
            logger.debug("Enabling global shortcut for Gnome")
            enabled_keybindings.append(_GNOME_SPEC_PATH)

        logger.debug("Saving global shortcut '%s' for Gnome", hotkey)
        _gsettings("set", _GNOME_BASE_SCHEMA, "custom-keybindings", repr(enabled_keybindings))
    elif DESKTOP_ID == "XFCE":
        cmd_prefix = ["xfconf-query", "--channel", "xfce4-keyboard-shortcuts"]
        all_shortcuts = subprocess.check_output([*cmd_prefix, "--list", "--verbose"]).decode().strip().split("\n")  # noqa: S603
        # Unset existing bindings
        for shortcut in all_shortcuts:
            if shortcut.endswith(launch_command):
                prop = shortcut.split()[0]
                subprocess.run([*cmd_prefix, "--reset", "--property", prop], check=True)  # noqa: S603

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
        subprocess.run(cmd, check=True)  # noqa: S603
    else:
        logger.warning("%s doesn't support setting hotkey for Desktop environment '%s'", app_display_name, DESKTOP_NAME)


_SET_HOTKEY_ERRORS = (OSError, subprocess.SubprocessError, TypeError, ValueError)


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
            # systemsettings5 is the old name; support both
            for syssettings_alias in ("systemsettings", "systemsettings5"):
                if which(syssettings_alias):
                    launch_detached([syssettings_alias, "kcm_keys"])
                    return

    @staticmethod
    def setup_default(default_hotkey: str) -> bool:
        if DESKTOP_ID == "PLASMA":
            hotkey = "Ctrl+Space"
            config_path = ["--file", "kglobalshortcutsrc", "--group", f"{app_id}.desktop", "--key"]
            kread = which("kreadconfig6") or "kreadconfig5"
            kwrite = which("kwriteconfig6") or "kwriteconfig5"
            config = subprocess.check_output([kread, *config_path, '"_launch"'])  # noqa: S603
            # only proceed if it's not already set up (don't override user prefs)
            if config.decode().strip():
                logger.debug("%s Plasma global shortcut already created", app_display_name)
                return False
            if default_hotkey not in {"<Primary>space", "<Control>space"}:
                # We don't want to convert the hotkey, so instead we just hard code it
                logger.warning("Ignoring hotkey argument %s and using default '%s'", default_hotkey, hotkey)
            logger.debug("Executing kwriteconfig commands to add Plasma global shortcut for '%s'", hotkey)
            subprocess.run([kwrite, *config_path, "_k_friendly_name", app_display_name], check=True)  # noqa: S603
            subprocess.run([kwrite, *config_path, "_launch", f"{hotkey},none,{app_display_name}"], check=True)  # noqa: S603
            from ulauncher.utils.systemd_controller import SystemdController

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
                except _SET_HOTKEY_ERRORS:
                    logger.debug("Shortcut grab failed for %s", accel, exc_info=True)
                else:
                    return True
            return False
        return False

    @staticmethod
    def current_accelerator() -> str:
        from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK
        from ulauncher.utils.settings import Settings

        if DESKTOP_ID == "GNOME":
            grabbed = _current_gnome_grab()
            if grabbed:
                return grabbed
        return Settings.load().hotkey_show_app or DEFAULT_FALLBACK

    @staticmethod
    def apply_accelerator(accel: str) -> bool:
        """Write a captured shortcut to the DE's keybinding store and settings."""
        from ulauncher.modes.launcher.shortcut import DEFAULT_FALLBACK
        from ulauncher.utils.eventbus import EventBus
        from ulauncher.utils.settings import Settings

        requested = accel or DEFAULT_FALLBACK
        previous = HotkeyController.current_accelerator()
        try:
            if IS_SUPPORTED and DESKTOP_ID != "PLASMA":
                _set_hotkey(requested)
            Settings.load().save({"hotkey_show_app": requested})
            EventBus().emit("app:rebind_hotkey", requested)
        except _SET_HOTKEY_ERRORS:
            logger.debug("Shortcut grab failed for %s", requested, exc_info=True)
            restore = hotkey_to_restore_after_failed_grab(False, previous)
            if restore:
                try:
                    if IS_SUPPORTED and DESKTOP_ID != "PLASMA":
                        _set_hotkey(restore)
                except _SET_HOTKEY_ERRORS:
                    logger.debug("Could not restore previous shortcut grab", exc_info=True)
            return False
        else:
            return True

    @staticmethod
    def bind_session_hotkey(hotkey: str, on_toggle: Callable[[], None]) -> Any:
        """Bind the toggle via the GlobalShortcuts portal on compositors without a DE store.

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

    @staticmethod
    def rebind_portal(accel: str) -> None:
        portal = HotkeyController._portal_session
        if portal is not None:
            portal.start(accel, app_id)


def _current_gnome_grab() -> str:
    try:
        raw = _gsettings("get", f"{_GNOME_SPEC_SCHEMA}:{_GNOME_SPEC_PATH}", "binding")
        value = ast.literal_eval(raw)
        return value if isinstance(value, str) else ""
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError):
        return ""
