from __future__ import annotations

from gi.repository import Adw

from ulauncher.ui.preferences.adw_rows import plain_action_row
from ulauncher.utils.launch_detached import open_detached

_GOSHOS_SPEC = "https://github.com/goshitsarch-eng/spotlight-goshos"

_KEYBOARD_ROWS = (
    ("Ctrl+Space", "Open or dismiss the launcher"),
    ("↑ / ↓, Tab, Page Up / Page Down", "Move through results"),
    ("Ctrl+J / Ctrl+K", "Move through results. Ctrl+N / Ctrl+P do the same"),
    (
        "Home / End",
        "Jump to the first or last row only when the caret is already at that edge of the query",
    ),
    ("Enter", "Activate the selected result, or click / tap the row"),
    (
        "Alt+1 … Alt+9",
        "Activate that numbered row when number hints are on. A pending Checking path does not fall through",
    ),
    (
        "Esc",
        "Dismiss. Click or tap outside also closes and claims the press so the window underneath does not activate",
    ),
)

_PREFIX_ROWS = (
    ("=", "Calculator. =2^8 and =42 are math; a bare 42 is not"),
    ("@", "Web search immediately"),
    ("#", "GNOME Settings. Needs a space so #ff0000 stays a color"),
    ("$", "Open windows. Needs a space so $HOME stays a path"),
    (".", "Recent files. Needs a space so .bashrc stays a path"),
    ("!", "Run a command as argv, not a shell. Off by default"),
)


def build_help_page() -> Adw.PreferencesPage:
    page = Adw.PreferencesPage(title="Help", icon_name="help-browser-symbolic")

    keyboard = Adw.PreferencesGroup(
        title="Keyboard",
        description="Open with Ctrl+Space and begin typing. Navigation matches Spotlight-goshos.",
    )
    for title, subtitle in _KEYBOARD_ROWS:
        keyboard.add(plain_action_row(title, subtitle))
    page.add(keyboard)

    prefixes = Adw.PreferencesGroup(
        title="Prefixes",
        description="Walker-style prefixes jump to one provider. Turn them off in Features.",
    )
    for title, subtitle in _PREFIX_ROWS:
        prefixes.add(plain_action_row(title, subtitle))
    page.add(prefixes)

    spec = Adw.PreferencesGroup(title="Spec")
    spec_row = plain_action_row("Spotlight-goshos", "Feature list this launcher follows")
    spec_row.set_activatable(True)
    spec_row.connect("activated", lambda *_args: open_detached(_GOSHOS_SPEC))
    spec.add(spec_row)
    page.add(spec)
    return page
