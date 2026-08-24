from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.apps import app_base_name, app_match_tier, unique_by_base_name


def test_app_base_name_strips_channel_suffix() -> None:
    assert app_base_name("Firefox ESR") == "firefox"
    assert app_base_name("Firefox") == "firefox"
    assert app_base_name("GNOME Builder") == "gnome builder"


def test_unique_by_base_name_keeps_first_sorted() -> None:
    esr = SimpleNamespace(name="Firefox ESR", app_id="firefox-esr.desktop")
    stable = SimpleNamespace(name="Firefox", app_id="firefox.desktop")
    unique = unique_by_base_name([stable, esr], 6)
    assert [app.name for app in unique] == ["Firefox"]


def test_app_match_tier_prefers_name_prefix() -> None:
    firefox = SimpleNamespace(
        name="Firefox",
        description="Web Browser",
        app_id="org.mozilla.firefox.desktop",
        keywords=["browser"],
    )
    assert app_match_tier(firefox, "fire") == 0
    assert app_match_tier(firefox, "browser") == 3
    assert app_match_tier(firefox, "mozilla") == 4
    assert app_match_tier(firefox, "zzz") == -1
