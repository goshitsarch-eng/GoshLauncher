from __future__ import annotations

from ulauncher.modes.launcher.prefs_live import (
    keys_from_save,
    live_pref_actions,
    should_apply_layout_immediately,
    should_run_live_idle,
    should_schedule_live_idle,
)


def test_keys_from_save_reads_dict_and_kwargs() -> None:
    assert keys_from_save({"look_id": "popos"}) == ("look_id",)
    assert keys_from_save(enable_calculator=False) == ("enable_calculator",)
    assert keys_from_save() == ()


def test_live_pref_actions_match_goshos_handlers() -> None:
    assert live_pref_actions(["look_id"]) == frozenset({"restyle", "repaint"})
    assert live_pref_actions(["base_width"]) == frozenset({"layout"})
    assert live_pref_actions(["popup_position"]) == frozenset({"position"})
    assert live_pref_actions(["show_search_icon"]) == frozenset({"search-icon"})
    assert live_pref_actions(["results_max_height"]) == frozenset({"fit-height"})
    assert live_pref_actions(["row_density"]) == frozenset({"restyle", "repaint"})
    assert live_pref_actions(["enable_calculator"]) == frozenset({"repaint"})
    assert live_pref_actions(["web_search_engine"]) == frozenset({"repaint"})
    assert live_pref_actions(["enable_prefix_modes", "enable_command_run"]) == frozenset({"repaint"})
    assert live_pref_actions(["theme_name"]) == frozenset()
    assert live_pref_actions(["applied_look"]) == frozenset()
    assert live_pref_actions(["look_id", "enable_calculator"]) == frozenset({"restyle", "repaint"})


def test_live_idle_gates_match_goshos() -> None:
    assert should_schedule_live_idle(False, True) is True
    assert should_schedule_live_idle(True, True) is False
    assert should_schedule_live_idle(False, False) is False
    assert should_run_live_idle(True) is True
    assert should_run_live_idle(False) is False
    assert should_apply_layout_immediately(False) is True
    assert should_apply_layout_immediately(True) is False
