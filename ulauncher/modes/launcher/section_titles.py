"""Section titles, ported from spotlight-goshos sectionTitles.js."""

from __future__ import annotations

SECTION_TITLES = {
    "app": "Applications",
    "app-action": "Actions",
    "calculator": "Calculator",
    "unit": "Units",
    "units": "Units",
    "color": "Color",
    "window": "Windows",
    "window-close": "Close Window",
    "workspace": "Workspaces",
    "system-action": "System Actions",
    "system": "System Actions",
    "settings": "Settings",
    "file": "Recent Files",
    "path": "Open Path",
    "place": "Folders",
    "bookmark": "Bookmarks",
    "time": "Clock",
    "clock": "Clock",
    "url": "Open Link",
    "command": "Run Command",
    "web": "Web Search",
}


def section_title(kind: str) -> str:
    return SECTION_TITLES.get(kind, "Results")
