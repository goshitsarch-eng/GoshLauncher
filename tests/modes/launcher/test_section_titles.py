from __future__ import annotations

from ulauncher.modes.launcher.no_results import no_results_detail, no_results_title, should_show_no_results
from ulauncher.modes.launcher.section_titles import section_title


def test_no_results_copy() -> None:
    assert no_results_title() == "No Results"
    assert no_results_detail("xyz") == 'No results for "xyz"'
    assert should_show_no_results("xyz", 0) is True
    assert should_show_no_results("xyz", 1) is False
    assert should_show_no_results("", 0) is False


def test_section_titles_match_goshos() -> None:
    assert section_title("app") == "Applications"
    assert section_title("app-action") == "Actions"
    assert section_title("place") == "Folders"
    assert section_title("path") == "Open Path"
    assert section_title("bookmark") == "Bookmarks"
    assert section_title("file") == "Recent Files"
    assert section_title("window-close") == "Close Window"
    assert section_title("workspace") == "Workspaces"
    assert section_title("system") == "System Actions"
    assert section_title("web") == "Web Search"
    assert section_title("unknown") == "Results"
