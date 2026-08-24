from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.parental import (
    PARENTAL_GIVE_UP_MS,
    ParentalControls,
    app_is_allowed,
    reset_parental_controls,
    should_offer_app,
)


def test_should_offer_app_hides_blocked_when_ready() -> None:
    assert should_offer_app(True, True, False, False) is False
    assert should_offer_app(True, True, True, False) is True
    assert should_offer_app(False, True, True, False) is False


def test_should_offer_app_gives_up_after_timeout() -> None:
    assert should_offer_app(True, False, False, False) is False
    assert should_offer_app(True, False, False, True) is True


def test_parental_controls_give_up_ms() -> None:
    clock = {"now": 0.0}

    def now() -> float:
        return clock["now"]

    controls = ParentalControls(now=now, probe=lambda: {"initialized": False, "allows": lambda _app_id: False})
    assert controls.initialized is False
    assert controls.gave_up is False
    clock["now"] = (PARENTAL_GIVE_UP_MS / 1000) + 0.01
    assert controls.gave_up is True
    assert controls.allows_app_id("blocked.desktop") is True


def test_app_is_allowed_uses_singleton() -> None:
    blocked = ParentalControls(probe=lambda: {"initialized": True, "allows": lambda app_id: app_id != "games.desktop"})
    reset_parental_controls(blocked)
    try:
        assert app_is_allowed(SimpleNamespace(app_id="firefox.desktop")) is True
        assert app_is_allowed(SimpleNamespace(app_id="games.desktop")) is False
    finally:
        reset_parental_controls(None)
