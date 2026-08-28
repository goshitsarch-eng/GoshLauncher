"""Parental-controls filtering, ported from Spotlight-goshos appReady.js."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# malcontent D-Bus can fail without ever setting initialized
PARENTAL_GIVE_UP_MS = 5000


def should_offer_app(
    desktop_should_show: bool,
    parental_initialized: bool,
    parental_allows: bool,
    parental_gave_up: bool,
) -> bool:
    if not desktop_should_show:
        return False
    if parental_initialized:
        return parental_allows
    return parental_gave_up is True


class ParentalControls:
    def __init__(
        self,
        *,
        now: Callable[[], float] = time.monotonic,
        probe: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._now = now
        self._started = now()
        state = (probe or probe_malcontent)()
        self._initialized = bool(state.get("initialized"))
        self._allows_fn: Callable[[str], bool] = state.get("allows") or (lambda _app_id: True)

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def gave_up(self) -> bool:
        if self._initialized:
            return False
        return (self._now() - self._started) * 1000 >= PARENTAL_GIVE_UP_MS

    def allows_app_id(self, app_id: str) -> bool:
        allowed = True
        if self._initialized:
            allowed = bool(self._allows_fn(app_id))
        return should_offer_app(True, self._initialized, allowed, self.gave_up)


class _ParentalHolder:
    controls: ParentalControls | None = None


_holder = _ParentalHolder()


def probe_malcontent() -> dict[str, Any]:
    if not _malcontent_available():
        return {"initialized": True, "allows": lambda _app_id: True}
    allows = _load_app_filter()
    if allows is None:
        return {"initialized": False, "allows": lambda _app_id: False}
    return {"initialized": True, "allows": allows}


def parental_controls() -> ParentalControls:
    if _holder.controls is None:
        _holder.controls = ParentalControls()
    return _holder.controls


def reset_parental_controls(controls: ParentalControls | None = None) -> None:
    """Drop the cached probe. The next allows_app_id() re-runs it, retrying a lookup that failed."""
    _holder.controls = controls


def app_is_allowed(app: Any) -> bool:
    app_id = str(getattr(app, "app_id", "") or "")
    return parental_controls().allows_app_id(app_id)


def _malcontent_available() -> bool:
    try:
        from ulauncher.utils import qdbus

        # A session with no malcontent must not look like one whose probe is still
        # pending, or every app is withheld until PARENTAL_GIVE_UP_MS has passed.
        return qdbus.name_has_owner(qdbus.session_bus(), "org.freedesktop.Malcontent1")
    except Exception:
        return False


def _load_app_filter() -> Callable[[str], bool] | None:
    try:
        from ulauncher.utils import qdbus

        payload = qdbus.call(
            qdbus.session_bus(),
            "org.freedesktop.Malcontent1",
            "/org/freedesktop/Malcontent1/Manager",
            "org.freedesktop.Malcontent1.Manager",
            "GetAppFilter",
            [qdbus.uint32(os.getuid()), False],
            timeout_ms=200,
        )
        if payload is None:
            return None
        blocked: set[str] = set()
        if payload:
            first = payload[0]
            if isinstance(first, dict):
                apps = first.get("app-filter") or first.get("apps") or []
                blocked.update(str(item) for item in apps)
            elif isinstance(first, (list, tuple)):
                blocked.update(str(item) for item in first)

        def _allows_dbus(app_id: str) -> bool:
            return app_id not in blocked

        return _allows_dbus
    except Exception:
        logger.debug("Malcontent D-Bus app filter failed", exc_info=True)
        return None
