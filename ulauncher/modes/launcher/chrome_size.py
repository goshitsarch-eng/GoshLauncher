"""Size pref ranges from spotlight-goshos gschema and appearancePage.js."""

from __future__ import annotations

POPUP_WIDTH_MIN = 400
POPUP_WIDTH_MAX = 1200
POPUP_WIDTH_STEP = 20
POPUP_WIDTH_PAGE = 100
POPUP_WIDTH_DEFAULT = 600

RESULTS_HEIGHT_MIN = 160
RESULTS_HEIGHT_MAX = 800
RESULTS_HEIGHT_STEP = 20
RESULTS_HEIGHT_PAGE = 80
RESULTS_HEIGHT_DEFAULT = 400

MAX_RESULTS_MIN = 1
MAX_RESULTS_MAX = 20
MAX_RESULTS_STEP = 1
MAX_RESULTS_PAGE = 5
MAX_RESULTS_DEFAULT = 6

ICON_SIZE_MIN = 16
ICON_SIZE_MAX = 64
ICON_SIZE_STEP = 2
ICON_SIZE_PAGE = 8
ICON_SIZE_DEFAULT = 28


def clamp_int(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value)))


def clamp_popup_width(value: int) -> int:
    return clamp_int(value, POPUP_WIDTH_MIN, POPUP_WIDTH_MAX)


def clamp_results_max_height(value: int) -> int:
    return clamp_int(value, RESULTS_HEIGHT_MIN, RESULTS_HEIGHT_MAX)


def clamp_max_results(value: int) -> int:
    return clamp_int(value, MAX_RESULTS_MIN, MAX_RESULTS_MAX)


def clamp_icon_size(value: int) -> int:
    return clamp_int(value, ICON_SIZE_MIN, ICON_SIZE_MAX)
