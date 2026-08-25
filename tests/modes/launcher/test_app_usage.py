from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher.app_usage import (
    gnome_app_usage_path,
    gnome_app_usage_score,
    load_gnome_app_usage_scores,
    parse_gnome_app_usage,
    reset_gnome_app_usage_cache,
)

GNOME_USAGE_XML = """<?xml version="1.0"?>
<application-state>
  <context>
    <application id="firefox.desktop" score="12.5" last-seen="1700000000"/>
    <application id="org.gnome.Nautilus.desktop" score="3" last-seen="1700000001"/>
    <application id="broken.desktop" score="nope" last-seen="1"/>
    <application score="9"/>
  </context>
</application-state>
"""


def test_parse_gnome_app_usage_scores() -> None:
    scores = parse_gnome_app_usage(GNOME_USAGE_XML)
    assert scores["firefox.desktop"] == 12.5
    assert scores["org.gnome.Nautilus.desktop"] == 3.0
    assert scores["broken.desktop"] == 0.0
    assert "" not in scores
    assert parse_gnome_app_usage("") == {}
    assert parse_gnome_app_usage("<not-xml") == {}


def test_gnome_app_usage_path_uses_xdg_data_home() -> None:
    path = gnome_app_usage_path({"XDG_DATA_HOME": "/tmp/data"}, home="/home/u")
    assert path == Path("/tmp/data/gnome-shell/application_state")
    fallback = gnome_app_usage_path({}, home="/home/u")
    assert fallback == Path("/home/u/.local/share/gnome-shell/application_state")


def test_load_gnome_app_usage_scores_caches_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_gnome_app_usage_cache()
    state = tmp_path / "application_state"
    state.write_text(GNOME_USAGE_XML, encoding="utf-8")
    monkeypatch.setattr("ulauncher.modes.launcher.app_usage.gnome_app_usage_path", lambda **_kwargs: state)
    scores = load_gnome_app_usage_scores()
    assert gnome_app_usage_score("firefox.desktop") == 12.5
    assert gnome_app_usage_score("missing.desktop") is None
    assert scores["firefox.desktop"] == 12.5
    state.write_text(
        '<application-state><application id="firefox.desktop" score="99"/></application-state>',
        encoding="utf-8",
    )
    reset_gnome_app_usage_cache()
    assert load_gnome_app_usage_scores()["firefox.desktop"] == 99.0
    reset_gnome_app_usage_cache()
    missing = tmp_path / "missing"
    monkeypatch.setattr("ulauncher.modes.launcher.app_usage.gnome_app_usage_path", lambda **_kwargs: missing)
    assert load_gnome_app_usage_scores() == {}
    assert gnome_app_usage_score("") is None
