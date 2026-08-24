"""Close when a system modal appears (goshos ``system-modal-opened``).

GNOME Shell emits that in-process. A GTK app watches D-Bus names that appear
when screenshot UIs spawn as separate processes, and yields the layer-shell
keyboard so an in-process shell modal can take focus and trigger focus-loss.
"""

from __future__ import annotations

from typing import Any

# Always-owned names such as org.gnome.Shell.Screenshot are skipped: gnome-shell
# holds those for the whole session, so NameOwnerChanged would never fire at
# screenshot time.
SYSTEM_MODAL_BUS_NAMES = frozenset(
    {
        "org.gnome.Screenshot",
        "org.gnome.Snapshot",
    }
)

SYSTEM_MODAL_WATCHES = (
    (
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameOwnerChanged",
    ),
)


def name_owner_changed_should_close(name: object, old_owner: object, new_owner: object) -> bool:
    if str(name) not in SYSTEM_MODAL_BUS_NAMES:
        return False
    new = str(new_owner or "")
    old = str(old_owner or "")
    return bool(new) and new != old


def launcher_keyboard_mode(keyboard_mode: Any) -> Any:
    """Prefer ON_DEMAND so polkit/screenshot can steal keys; EXCLUSIVE if that enum is missing."""
    on_demand = getattr(keyboard_mode, "ON_DEMAND", None)
    if on_demand is not None:
        return on_demand
    return keyboard_mode.EXCLUSIVE
