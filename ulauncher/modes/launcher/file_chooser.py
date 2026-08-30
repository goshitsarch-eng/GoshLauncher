"""Compatibility helpers for extracting local paths from file chooser objects."""

from __future__ import annotations

from typing import Any, Optional


def chooser_selected_path(chooser: Any) -> Optional[str]:
    """Return a local chooser path, or None for a non-local URI."""
    get_file = getattr(chooser, "get_file", None)
    file = get_file() if callable(get_file) else None
    if file is not None:
        get_path = getattr(file, "get_path", None)
        path = get_path() if callable(get_path) else None
        if path:
            return str(path)
    get_filename = getattr(chooser, "get_filename", None)
    name = get_filename() if callable(get_filename) else None
    return str(name) if name else None


def should_take_chooser_path(response: int, accept_response: int) -> bool:
    return response == accept_response
