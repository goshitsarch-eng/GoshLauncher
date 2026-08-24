from __future__ import annotations

from ulauncher.modes.launcher.result_icon import (
    app_icon_or_fallback,
    result_icon_source,
    should_build_result_icon,
    window_icon_or_fallback,
)


def test_app_icon_falls_back_when_missing() -> None:
    class Throwing:
        def get_icon(self) -> None:
            message = "gone"
            raise RuntimeError(message)

    class Empty:
        def get_icon(self) -> None:
            return None

    class Ok:
        def get_icon(self) -> object:
            return {"name": "ok"}

    assert app_icon_or_fallback(Throwing(), "missing-symbolic") == {"icon_name": "missing-symbolic"}
    assert app_icon_or_fallback(Empty(), "missing-symbolic") == {"icon_name": "missing-symbolic"}
    assert app_icon_or_fallback(None, "missing-symbolic") == {"icon_name": "missing-symbolic"}
    assert "gicon" in app_icon_or_fallback(Ok(), "missing-symbolic")
    assert should_build_result_icon(True) is True
    assert should_build_result_icon(False) is False
    assert window_icon_or_fallback(None) == "focus-windows-symbolic"
    assert result_icon_source({"icon": "utilities-terminal-symbolic"}) == {"icon_name": "utilities-terminal-symbolic"}
    assert result_icon_source({}) == {"icon_name": "application-x-executable-symbolic"}
