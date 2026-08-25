"""Result types for the Spotlight-style launcher."""

from __future__ import annotations

from typing import Any, Literal

from ulauncher.internals.result import Result


class LauncherResult(Result):
    """A launcher row with a kind/payload used by LauncherMode.activate_result."""

    kind: str = ""
    payload: dict[str, Any] = {}
    highlightable: bool = True
    searchable: bool = True
    activatable: bool = True
    actions: dict[str, dict[Literal["name", "icon"], str]] = {"activate": {"name": "Activate"}}


class SectionHeader(Result):
    compact: bool = True
    highlightable: bool = False
    searchable: bool = False
    name: str = ""
    description: str = ""
    icon: str = ""
    actions: dict[str, dict[Literal["name", "icon"], str]] = {}
