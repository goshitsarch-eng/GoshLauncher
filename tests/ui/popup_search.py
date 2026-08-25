"""GTK4 popup wired to UlauncherCore so tests can type Spotlight-goshos queries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests.ui.look_paint import ensure_look_css, patch_window_host, pump, wait_popup_styled

_state = {"seq": 0}


class SearchPopup:
    """A real UlauncherWindow whose query_changed runs LauncherMode."""

    def __init__(self, win: Any, app: Any, launcher: Any, settings: Any, stack: Any) -> None:
        self.win = win
        self.app = app
        self.launcher = launcher
        self.settings = settings
        self.stack = stack

    def kinds(self) -> list[str]:
        return [
            str(getattr(row, "kind", ""))
            for row in self.win.results_view.get_result_objects()
            if getattr(row, "kind", "")
        ]

    def names(self) -> list[str]:
        return [str(row.name) for row in self.win.results_view.get_result_objects() if getattr(row, "name", "")]

    def type_query(self, text: str) -> list[str]:
        from gi.repository import GLib

        self.win.set_input(text)
        ctx = GLib.MainContext.default()
        # Path/bookmark/window lookups paint with final=False; ResultBuffer then waits 50ms.
        deadline = GLib.get_monotonic_time() + 400_000
        kinds: list[str] = []
        while GLib.get_monotonic_time() < deadline:
            ctx.iteration(False)
            self.launcher.flush_lookups()
            kinds = self.kinds()
            if kinds:
                settle = GLib.get_monotonic_time() + 80_000
                while GLib.get_monotonic_time() < settle:
                    ctx.iteration(False)
                self.launcher.flush_lookups()
                return self.kinds()
        return kinds

    def press(self, keyval: int, state: object = 0) -> bool:
        return bool(self.win.on_input_key_press(SimpleNamespace(), keyval, 0, state))

    def close(self) -> None:
        closer = getattr(self.win, "close", None)
        if callable(closer):
            closer()
        closer = getattr(self.stack, "close", None)
        if callable(closer):
            closer()
        pump(8)


def open_search_popup(
    *,
    application_id: str | None = None,
    settings: Any | None = None,
    home_apps: list | None = None,
    home_windows: list | None = None,
) -> SearchPopup:
    from contextlib import ExitStack
    from unittest.mock import patch

    from gi.repository import Adw, Gio

    from ulauncher.core import UlauncherCore
    from ulauncher.modes.launcher.mode import LauncherMode
    from ulauncher.ui.ulauncher_window import UlauncherWindow
    from ulauncher.utils.settings import Settings

    ensure_look_css()
    Adw.init()
    _state["seq"] = int(_state["seq"]) + 1
    app_id = application_id or f"io.ulauncher.SearchProbe{_state['seq']}"
    launcher = LauncherMode()
    conf = settings if settings is not None else Settings()
    apps = list(home_apps) if home_apps is not None else []
    windows = list(home_windows) if home_windows is not None else []

    class SearchProbeApp(Adw.Application):
        query = ""
        activated: Any = None

        def __init__(self) -> None:
            super().__init__(application_id=app_id, flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.core = UlauncherCore()

        def window_ready(self) -> None:
            self.core.load_triggers(force=True)
            self.core.set_query(self.query, self.show_results)

        def query_changed(self, query_str: str) -> None:
            self.query = (query_str or "").lstrip()
            self.core.set_query(self.query, self.show_results)

        def show_results(self, update: object) -> None:
            for window in self.get_windows():
                render = getattr(window, "show_results", None)
                if callable(render):
                    render(update)
                    return

        def show_preferences(self, *_args: object, **_kwargs: object) -> None:
            return

        def request_close(self, _save_query: bool = False) -> None:
            return

        def close_launcher(self, *_args: object, **_kwargs: object) -> None:
            return

        def set_query(self, value: str, update_input: bool = True) -> None:
            self.query = value
            if not update_input:
                return
            for window in self.get_windows():
                setter = getattr(window, "set_input", None)
                if callable(setter):
                    setter(self.query)
                    return

        def activate_result(self, result: object, alt: bool) -> None:
            self.activated = (result, alt)

        def handle_backspace(self, _query_str: str) -> bool:
            return False

    app = SearchProbeApp()
    app.register()
    stack = ExitStack()
    patch_window_host(stack)
    stack.enter_context(patch("ulauncher.core.get_modes", lambda: [launcher]))
    stack.enter_context(patch("ulauncher.internals.result_buffer.RENDER_THROTTLE", 0))
    stack.enter_context(patch.object(Settings, "load", classmethod(lambda _cls, **_kwargs: conf)))
    stack.enter_context(patch("ulauncher.modes.launcher.apps.home_apps", lambda limit: apps[:limit]))
    stack.enter_context(patch("ulauncher.modes.launcher.windows.cached_windows", lambda: windows))
    stack.enter_context(patch("ulauncher.modes.launcher.windows.ensure_windows", lambda _on_ready: None))
    win = UlauncherWindow(application=app)
    try:
        wait_popup_styled(win)
        win.deferred_init()
        launcher.flush_lookups()
        pump(16)
    except RuntimeError:
        win.close()
        stack.close()
        pump(8)
        raise
    return SearchPopup(win, app, launcher, conf, stack)
