from __future__ import annotations

from ulauncher.modes.launcher.chrome_size import (
    ICON_SIZE_DEFAULT,
    ICON_SIZE_MAX,
    ICON_SIZE_MIN,
    ICON_SIZE_PAGE,
    ICON_SIZE_STEP,
    MAX_RESULTS_DEFAULT,
    MAX_RESULTS_MAX,
    MAX_RESULTS_MIN,
    MAX_RESULTS_PAGE,
    MAX_RESULTS_STEP,
    POPUP_WIDTH_DEFAULT,
    POPUP_WIDTH_MAX,
    POPUP_WIDTH_MIN,
    POPUP_WIDTH_PAGE,
    POPUP_WIDTH_STEP,
    RESULTS_HEIGHT_DEFAULT,
    RESULTS_HEIGHT_MAX,
    RESULTS_HEIGHT_MIN,
    RESULTS_HEIGHT_PAGE,
    RESULTS_HEIGHT_STEP,
    clamp_icon_size,
    clamp_max_results,
    clamp_popup_width,
    clamp_results_max_height,
)


def test_size_ranges_match_goshos_gschema() -> None:
    assert (POPUP_WIDTH_MIN, POPUP_WIDTH_MAX, POPUP_WIDTH_DEFAULT) == (400, 1200, 600)
    assert (POPUP_WIDTH_STEP, POPUP_WIDTH_PAGE) == (20, 100)
    assert (RESULTS_HEIGHT_MIN, RESULTS_HEIGHT_MAX, RESULTS_HEIGHT_DEFAULT) == (160, 800, 400)
    assert (RESULTS_HEIGHT_STEP, RESULTS_HEIGHT_PAGE) == (20, 80)
    assert (MAX_RESULTS_MIN, MAX_RESULTS_MAX, MAX_RESULTS_DEFAULT) == (1, 20, 6)
    assert (MAX_RESULTS_STEP, MAX_RESULTS_PAGE) == (1, 5)
    assert (ICON_SIZE_MIN, ICON_SIZE_MAX, ICON_SIZE_DEFAULT) == (16, 64, 28)
    assert (ICON_SIZE_STEP, ICON_SIZE_PAGE) == (2, 8)


def test_clamp_size_prefs() -> None:
    assert clamp_popup_width(399) == 400
    assert clamp_popup_width(1201) == 1200
    assert clamp_popup_width(600) == 600
    assert clamp_results_max_height(80) == 160
    assert clamp_results_max_height(900) == 800
    assert clamp_max_results(0) == 1
    assert clamp_max_results(21) == 20
    assert clamp_icon_size(8) == 16
    assert clamp_icon_size(80) == 64
