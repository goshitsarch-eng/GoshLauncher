from __future__ import annotations

import pytest

from tests.ui.conftest import GTK4_AVAILABLE

pytestmark = pytest.mark.skipif(not GTK4_AVAILABLE, reason="GTK 4 is not available")


def test_refresh_does_not_replay_the_active_selection() -> None:
    import gi

    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gtk

    from ulauncher.ui.preferences.utils.sidebar_layout import SidebarItem, SidebarLayout

    Adw.init()
    activated: list[str] = []

    def items(label: str) -> list[SidebarItem]:
        return [
            SidebarItem(
                id=f"ext{index}",
                icon=Gtk.Label(),
                name=f"Ext {index}",
                label=label,
                on_activate=lambda item: activated.append(item.id),
            )
            for index in range(2)
        ]

    layout = SidebarLayout()
    layout.set_items(items("running"), "ext0")
    assert activated == ["ext0"]

    # The extensions page rebuilds this list every second as extension status changes. Replaying
    # the selection re-ran the callback that rebuilds the detail pane, throwing away edits.
    activated.clear()
    layout.set_items(items("stopped"), "ext0")
    assert activated == []

    # selecting a different item still activates it
    layout.set_items(items("stopped"), "ext1")
    assert activated == ["ext1"]
