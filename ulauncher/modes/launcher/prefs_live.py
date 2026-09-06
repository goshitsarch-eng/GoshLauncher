"""Apply preference writes while the popup is open, from goshos launcherPopup.js."""

from __future__ import annotations

from typing import Any, Iterable

# GSettings changed:: keys in goshos map onto these Settings fields.
RESTYLE_KEYS = frozenset({"look_id", "row_density"})
LAYOUT_KEYS = frozenset({"base_width"})
POSITION_KEYS = frozenset({"popup_position", "render_on_screen"})
SEARCH_ICON_KEYS = frozenset({"show_search_icon"})
FIT_HEIGHT_KEYS = frozenset({"results_max_height"})
REPAINT_KEYS = frozenset(
    {
        "look_id",
        "row_density",
        "icon_size",
        "show_section_headers",
        "show_result_icons",
        "show_descriptions",
        "show_result_numbers",
        "result_order",
        "max_per_category",
        "enable_empty_suggestions",
        "enable_application_mode",
        "enable_app_actions",
        "enable_calculator",
        "enable_unit_convert",
        "enable_color_hex",
        "enable_window_search",
        "enable_system_actions",
        "enable_settings_search",
        "enable_recent_files",
        "enable_url_open",
        "enable_path_open",
        "enable_places",
        "enable_bookmarks",
        "enable_time_date",
        "enable_command_run",
        "enable_prefix_modes",
        "show_web_search",
        "web_search_engine",
    }
)

ACTION_RESTYLE = "restyle"
ACTION_LAYOUT = "layout"
ACTION_POSITION = "position"
ACTION_SEARCH_ICON = "search-icon"
ACTION_FIT_HEIGHT = "fit-height"
ACTION_REPAINT = "repaint"


def keys_from_save(*args: Any, **kwargs: Any) -> tuple[str, ...]:
    try:
        payload = dict(*args, **kwargs)
    except (TypeError, ValueError):
        return ()
    return tuple(str(key) for key in payload)


def live_pref_actions(keys: Iterable[str]) -> frozenset[str]:
    """Which popup updates a settings write should run, matching goshos connectObject."""
    key_set = frozenset(keys)
    actions: set[str] = set()
    if key_set & RESTYLE_KEYS:
        actions.add(ACTION_RESTYLE)
    if key_set & LAYOUT_KEYS:
        actions.add(ACTION_LAYOUT)
    if key_set & POSITION_KEYS:
        actions.add(ACTION_POSITION)
    if key_set & SEARCH_ICON_KEYS:
        actions.add(ACTION_SEARCH_ICON)
    if key_set & FIT_HEIGHT_KEYS:
        actions.add(ACTION_FIT_HEIGHT)
    if key_set & REPAINT_KEYS:
        actions.add(ACTION_REPAINT)
    return frozenset(actions)


def should_schedule_live_idle(already_pending: bool, is_open: bool) -> bool:
    # dconf can land while a key is still dispatching; coalesce to one idle
    return is_open and not already_pending


def should_run_live_idle(is_open: bool) -> bool:
    return is_open


def should_apply_layout_immediately(is_open: bool) -> bool:
    # closed popups still stamp width and results max-height so the next open fits
    return not is_open
