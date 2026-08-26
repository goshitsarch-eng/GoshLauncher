from __future__ import annotations

from gi.repository import Adw

from ulauncher import version
from ulauncher.ui.preferences.adw_rows import plain_action_row
from ulauncher.utils.launch_detached import open_detached

_GOSHOS_SPEC = "https://github.com/goshitsarch-eng/spotlight-goshos"
_ULAUNCHER = "https://github.com/Ulauncher/Ulauncher"
_GOSHLAUNCHER = "https://github.com/goshitsarch-eng/GoshLauncher"

# GPL-3.0 5(a): a modified Ulauncher has to say so where users can see it. The goshos About page
# is fixed at three rows, so the fork's credits sit here with the rest of the GTK-host docs.
_CREDIT_ROWS = (
    (
        "Ulauncher",
        "Upstream code base. \u00a9 2015 Aleksandr Gornostal and contributors, GPL-3.0. Extension API 3.0 is theirs",
        _ULAUNCHER,
    ),
    (
        "Spotlight-goshos",
        "Design and behaviour reference: the search order, looks, prefixes, and this keyboard map",
        _GOSHOS_SPEC,
    ),
    (
        "GoshLauncher",
        "This fork. Source, issues, and the full credits in AUTHORS",
        _GOSHLAUNCHER,
    ),
)

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


def add_usage_groups(page: Adw.PreferencesPage) -> None:
    """Keyboard and prefix docs on Desktop. Goshos About is only title, Looks, and host."""
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

    credits_group = Adw.PreferencesGroup(
        title="Credits",
        description=(
            f"GoshLauncher {version} \u00b7 GNU GPL v3.0. A fork of Ulauncher v6, redesigned to follow "
            "Spotlight-goshos. Neither project endorses it."
        ),
    )
    for title, subtitle, url in _CREDIT_ROWS:
        row = plain_action_row(title, subtitle)
        row.set_activatable(True)
        row.connect("activated", lambda _row, link=url: open_detached(link))
        credits_group.add(row)
    page.add(credits_group)
