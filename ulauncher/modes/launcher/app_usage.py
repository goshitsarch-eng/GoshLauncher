"""Read GNOME Shell AppUsage scores from application_state, like Shell.AppUsage."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path


class _GnomeUsageCache:
    scores: dict[str, float] | None = None
    mtime: float = -1.0
    path: str = ""


_cache = _GnomeUsageCache()


def gnome_app_usage_path(environ: Mapping[str, str] | None = None, home: str | None = None) -> Path:
    env = os.environ if environ is None else environ
    data = env.get("XDG_DATA_HOME") or str(Path(home or Path.home()) / ".local/share")
    return Path(data) / "gnome-shell" / "application_state"


def reset_gnome_app_usage_cache() -> None:
    _cache.scores = None
    _cache.mtime = -1.0
    _cache.path = ""


def parse_gnome_app_usage(text: str) -> dict[str, float]:
    # gnome-shell src/shell-app-usage.c writes <application id= score= last-seen=/>
    if not text or not text.strip():
        return {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    scores: dict[str, float] = {}
    for node in root.iter("application"):
        app_id = str(node.attrib.get("id") or "")
        if not app_id:
            continue
        try:
            scores[app_id] = float(node.attrib.get("score") or 0)
        except ValueError:
            scores[app_id] = 0.0
    return scores


def load_gnome_app_usage_scores(path: Path | None = None) -> dict[str, float]:
    target = path or gnome_app_usage_path()
    ident = str(target)
    try:
        stat = target.stat()
    except OSError:
        _cache.scores = {}
        _cache.mtime = -1.0
        _cache.path = ident
        return {}
    if _cache.scores is not None and _cache.path == ident and _cache.mtime == stat.st_mtime:
        return _cache.scores
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        scores: dict[str, float] = {}
    else:
        scores = parse_gnome_app_usage(text)
    _cache.scores = scores
    _cache.mtime = stat.st_mtime
    _cache.path = ident
    return scores


def gnome_app_usage_score(app_id: str) -> float | None:
    if not app_id:
        return None
    scores = load_gnome_app_usage_scores()
    if app_id not in scores:
        return None
    return scores[app_id]
