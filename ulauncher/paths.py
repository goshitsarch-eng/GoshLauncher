import os
import sys

# spec: https://specifications.freedesktop.org/menu-spec/latest/ar01s02.html
APPLICATION = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
# ULAUNCHER_SYSTEM_PREFIX can be used by third party packagers like Nix
# If not set, derive sys prefix from binary location likely /usr, /usr/local, or ~/.local
SYSTEM_PREFIX = os.environ.get("ULAUNCHER_SYSTEM_PREFIX", os.path.dirname(BIN_DIR))
# ULAUNCHER_SYSTEM_DATA_DIR is used when running in dev mode from source and during tests
ASSETS = os.path.abspath(os.environ.get("ULAUNCHER_SYSTEM_DATA_DIR", f"{SYSTEM_PREFIX}/share/ulauncher"))
HOME = os.path.expanduser("~")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", f"{HOME}/.cache"), "ulauncher")
XDG_DATA_DIRS = os.environ.get("XDG_DATA_DIRS", f"/usr/local/share/{os.path.pathsep}/usr/share/").split(os.path.pathsep)
# The XDG base dirs themselves, for the files other apps own (GTK bookmarks, recently-used.xbel)
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or f"{HOME}/.config"
XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME") or f"{HOME}/.local/share"
CONFIG = os.path.join(XDG_CONFIG_HOME, "ulauncher")
DATA = os.path.join(XDG_DATA_HOME, "ulauncher")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME", f"{HOME}/.local/state"), "ulauncher")
USER_EXTENSIONS = os.path.join(DATA, "extensions")
# Sibling of the installed extensions so the post-install swap is a same-filesystem rename.
EXTENSIONS_STAGING = os.path.join(USER_EXTENSIONS, ".staging")
ALL_EXTENSIONS_DIRS = [USER_EXTENSIONS, *[os.path.join(p, "ulauncher", "extensions") for p in XDG_DATA_DIRS]]
EXTENSIONS_CONFIG = os.path.join(CONFIG, "ext_preferences")
EXTENSIONS_STATE = os.path.join(STATE, "ext_state")
USER_THEMES = os.path.join(CONFIG, "user-themes")
SYSTEM_THEMES = os.path.join(ASSETS, "themes")
LOG_FILE = os.path.join(STATE, "last.log")
PREVIEW_LOG_FILE = os.path.join(STATE, "preview.log")
