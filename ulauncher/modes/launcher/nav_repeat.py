"""Drop duplicate nav presses without a Wayland event clock, from spotlight-goshos navRepeat.js."""

from __future__ import annotations

NAV_REPEAT_GAP_US = 50000


def should_ignore_nav_repeat(
    key: int,
    last_key: int,
    now_us: int,
    last_time_us: int,
    min_gap_us: int = 0,
) -> bool:
    gap = min_gap_us if min_gap_us > 0 else NAV_REPEAT_GAP_US
    if key != last_key:
        return False
    if last_time_us <= 0:
        return False
    return now_us - last_time_us < gap
