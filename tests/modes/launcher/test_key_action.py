from __future__ import annotations

from ulauncher.modes.launcher.key_action import (
    normalize_key_name,
    resolve_ctrl_nav,
    resolve_home_end_action,
    resolve_key_action,
)


def test_arrows_tab_shift_tab_and_alt_digits() -> None:
    assert resolve_key_action("Escape", False, False, False) == {"type": "close"}
    assert resolve_key_action("Down", False, False, False) == {"type": "move", "delta": 1}
    assert resolve_key_action("Tab", False, False, False) == {"type": "move", "delta": 1}
    assert resolve_key_action("Tab", True, False, False) == {"type": "move", "delta": -1}
    assert resolve_key_action("ISO_Left_Tab", False, False, False) == {"type": "move", "delta": -1}
    assert resolve_key_action("Page_Down", False, False, False) == {"type": "move", "delta": 5}
    assert resolve_key_action("Return", False, False, False) == {"type": "activate"}
    assert resolve_key_action("1", False, True, True) == {"type": "activate-index", "index": 0}
    assert resolve_key_action("1", False, True, False) == {"type": "propagate"}


def test_ctrl_nav_and_home_end_at_edges() -> None:
    assert resolve_ctrl_nav("j") == {"type": "move", "delta": 1}
    assert resolve_ctrl_nav("k") == {"type": "move", "delta": -1}
    assert resolve_ctrl_nav("n") == {"type": "move", "delta": 1}
    assert resolve_ctrl_nav("p") == {"type": "move", "delta": -1}
    assert resolve_ctrl_nav("a") is None
    assert resolve_home_end_action("Home", 0, 4) == {"type": "move", "delta": -999}
    assert resolve_home_end_action("Home", 2, 4) == {"type": "propagate"}
    assert resolve_home_end_action("End", 4, 4) == {"type": "move", "delta": 999}
    assert resolve_home_end_action("End", 1, 4) == {"type": "propagate"}


def test_keypad_aliases_match_goshos_nav() -> None:
    assert normalize_key_name("KP_Down") == "Down"
    assert normalize_key_name("KP_1") == "1"
    assert resolve_key_action("KP_Down", False, False, False) == {"type": "move", "delta": 1}
    assert resolve_key_action("KP_1", False, True, True) == {"type": "activate-index", "index": 0}
    assert resolve_home_end_action("KP_Home", 0, 4) == {"type": "move", "delta": -999}
