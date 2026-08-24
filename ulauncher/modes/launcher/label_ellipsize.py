"""Goshos ``labelEllipsize.js``: END-ellipsize so long titles never widen the popup."""

from __future__ import annotations

from typing import TypedDict

# Pango END, not MIDDLE. One line. FILL + x_expand so the row stays the panel width
# (goshos: ``Clutter.ActorAlign.FILL``, ``x_expand: true``).
ELLIPSIZE_END = "end"


class LabelEllipsizeSpec(TypedDict):
    ellipsize: str
    single_line: bool
    hexpand: bool
    max_width_chars: int


def label_ellipsize_spec() -> LabelEllipsizeSpec:
    return {
        "ellipsize": ELLIPSIZE_END,
        "single_line": True,
        "hexpand": True,
        "max_width_chars": 1,
    }
