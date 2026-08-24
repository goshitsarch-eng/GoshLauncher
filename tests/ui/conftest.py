from __future__ import annotations

import pytest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk  # noqa: F401

    GTK4_AVAILABLE = True
except (ValueError, ImportError):
    GTK4_AVAILABLE = False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if GTK4_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="GTK 4 is not available")
    for item in items:
        item.add_marker(skip)
