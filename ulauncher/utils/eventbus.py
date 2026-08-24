from __future__ import annotations

import logging
from collections import defaultdict
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from typing import TypeVar

    from typing_extensions import ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")

logger = logging.getLogger(__name__)

_listeners: dict[str, set[Callable[..., Any]]] = defaultdict(set)


class EventBus:
    namespace: str | None = None
    self_arg: Any = None
    skip_if_not_bound: bool

    def __init__(self, namespace: str | None = None, skip_if_not_bound: bool = False) -> None:
        # namespace is only used for on
        self.namespace = namespace
        self.skip_if_not_bound = skip_if_not_bound

    def set_self(self, self_arg: Any) -> None:
        self.self_arg = self_arg

    def _full_event_name(self, event_name: str) -> str:
        return ":".join(filter(None, (self.namespace, event_name)))

    def on(self, listener: Callable[P, R]) -> Callable[P, R]:
        @wraps(listener)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            if self.skip_if_not_bound and not self.self_arg:
                return
            if self.self_arg:
                args = (self.self_arg, *args)
            listener(*args, **kwargs)

        _listeners[self._full_event_name(listener.__name__)].add(wrapper)
        # return the original listener so the class method works as normal
        return listener

    def listen(self, event_name: str, listener: Callable[..., Any]) -> Callable[..., Any]:
        """Subscribe ``listener`` to a full event name. Returns the wrapper ``off`` must receive.

        ``@on`` keeps the method name as the event. Prefs windows need a removable
        handle because Gio.Settings outlives the widget (goshos prefsCombo.js).
        """

        @wraps(listener)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            if self.skip_if_not_bound and not self.self_arg:
                return
            if self.self_arg:
                args = (self.self_arg, *args)
            listener(*args, **kwargs)

        _listeners[event_name].add(wrapper)
        return wrapper

    def off(self, event_name: str, wrapper: Callable[..., Any]) -> None:
        _listeners[event_name].discard(wrapper)

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        # Exception barrier: a raising listener must not break the emitter or the other listeners
        for listener in _listeners[event_name]:
            try:
                listener(*args, **kwargs)
            except Exception:
                logger.exception("Unhandled error in listener for event %s", event_name)
