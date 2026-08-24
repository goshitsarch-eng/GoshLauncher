from __future__ import annotations

from ulauncher.modes.launcher.looks import LOOKS
from ulauncher.modes.launcher.prefs_combo import combo_selected_index
from ulauncher.modes.launcher.web import SEARCH_ENGINES


def test_combo_selected_index_matches_goshos() -> None:
    pop = next(index for index, look in enumerate(LOOKS) if look["id"] == "popos")
    assert combo_selected_index(LOOKS, "popos") == pop
    assert combo_selected_index(LOOKS, "missing") == -1
    kagi = next(index for index, engine in enumerate(SEARCH_ENGINES) if engine["id"] == "kagi")
    assert combo_selected_index(SEARCH_ENGINES, "kagi") == kagi
