from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock, PropertyMock

from pytest_mock import MockerFixture

from ulauncher.core import UlauncherCore, is_legacy_trigger_mode, launcher_has_local_hits, reject_async_paints
from ulauncher.internals import effects
from ulauncher.internals.query import Query
from ulauncher.internals.result import KeywordTrigger, Result
from ulauncher.modes.launcher.mode import LauncherMode
from ulauncher.modes.launcher.results import LauncherResult, SectionHeader
from ulauncher.modes.shortcuts.results import ShortcutResult


class TestStreamingResults:
    """Core wires streamed RENDER_RESULTS through the buffer; ResultBuffer owns the batching
    behavior itself (see tests/internals/test_result_buffer.py)."""

    def test_streamed_render_stamps_query_and_pick(self, mocker: MockerFixture) -> None:
        core = UlauncherCore()
        core.query = Query(None, "foo")
        mocker.patch.object(UlauncherCore, "last_query_result_pick", new_callable=PropertyMock, return_value="picked")
        outer = MagicMock()
        emit = core._mode_callback(None, outer)  # valid_mode=None skips the active-mode staleness guard

        r = Result(name="a")
        emit(effects.render_results([r], append=False, final=True))

        update = outer.call_args.args[0]
        assert update["results"] == [r]
        assert update["append"] is False
        assert str(update["query"]) == "foo"
        assert update["selected_name"] == "picked"

    def test_activating_drops_pending_stream_paint(self, mocker: MockerFixture) -> None:
        # A throttled paint armed mid-stream must not fire over what an activation renders next.
        core = UlauncherCore()
        captured: list[Callable[[], None]] = []
        mocker.patch(
            "ulauncher.internals.result_buffer.scheduling.timer",
            side_effect=lambda _d, fn: (captured.append(fn), MagicMock())[1],
        )
        render = MagicMock()
        core._mode_callback(None, render)(effects.render_results([Result(name="a")], final=False))
        assert captured  # a flush was scheduled
        render.assert_not_called()  # but it hasn't painted yet

        core.activate_result(Result(name="a"), MagicMock(), alt=True)
        captured[0]()  # the stale flush fires after activation
        render.assert_not_called()


def test_is_legacy_trigger_mode_by_class_name() -> None:
    class ShortcutMode:
        pass

    class ExtensionMode:
        pass

    class AppMode:
        pass

    assert is_legacy_trigger_mode(ShortcutMode()) is True  # type: ignore[arg-type]
    assert is_legacy_trigger_mode(ExtensionMode()) is True  # type: ignore[arg-type]
    assert is_legacy_trigger_mode(AppMode()) is False  # type: ignore[arg-type]


def test_launcher_has_local_hits_skips_headers_and_web() -> None:
    assert launcher_has_local_hits([]) is False
    assert launcher_has_local_hits([SectionHeader(name="Web")]) is False
    assert launcher_has_local_hits([LauncherResult(name="Search", kind="web")]) is False
    assert launcher_has_local_hits([SectionHeader(name="Web"), LauncherResult(name="Search", kind="web")]) is False
    assert launcher_has_local_hits([LauncherResult(name="Firefox", kind="app")]) is True


def test_reject_async_paints_forwards_to_launcher(mocker: MockerFixture) -> None:
    launcher = MagicMock()

    class Other:
        pass

    mocker.patch("ulauncher.core.get_modes", return_value=[launcher, Other()])
    reject_async_paints()
    launcher.reject_async_paint.assert_called_once_with()


def test_launcher_paint_does_not_merge_shortcut_triggers(mocker: MockerFixture) -> None:
    class ShortcutMode:
        pass

    class AppMode:
        pass

    core = UlauncherCore()
    launcher = LauncherMode()
    shortcut_mode = ShortcutMode()
    app_mode = AppMode()
    core._mode = launcher
    core.query = Query(None, "UniqueShortcutNameZZZ")
    trigger = KeywordTrigger(name="UniqueShortcutNameZZZ", keyword="zzz")
    app_trigger = KeywordTrigger(name="UniqueShortcutNameZZZ", keyword="app")
    core._trigger_cache[shortcut_mode] = [trigger]  # type: ignore[index]
    core._trigger_cache[app_mode] = [app_trigger]  # type: ignore[index]
    mocker.patch.object(core, "load_triggers")
    mocker.patch("ulauncher.core.get_modes", return_value=[launcher, shortcut_mode, app_mode])

    outer = MagicMock()
    emit = core._mode_callback(launcher, outer)
    row = LauncherResult(name="Firefox", kind="app")
    emit(effects.render_results([row], final=True))
    painted = outer.call_args.args[0]["results"]
    assert painted == [row]
    assert trigger not in painted
    assert app_trigger not in painted


def test_launcher_paint_does_not_add_default_search_fallbacks_next_to_web(mocker: MockerFixture) -> None:
    fallback = ShortcutResult(name="GoogleFallback", is_default_search=True, cmd="https://example/%s")

    class ShortcutMode:
        def get_fallback_results(self, _query_str: str) -> list[ShortcutResult]:
            return [fallback]

    core = UlauncherCore()
    launcher = LauncherMode()
    shortcut_mode = ShortcutMode()
    core._mode = launcher
    core.query = Query(None, "no-such-local-hit-zzz")
    mocker.patch.object(core, "load_triggers")
    mocker.patch("ulauncher.core.get_modes", return_value=[launcher, shortcut_mode])

    outer = MagicMock()
    emit = core._mode_callback(launcher, outer)
    emit(
        effects.render_results(
            [SectionHeader(name="Web"), LauncherResult(name="Search the web", kind="web")],
            final=True,
        )
    )
    assert fallback not in outer.call_args.args[0]["results"]

    emit(effects.render_results([LauncherResult(name="Firefox", kind="app")], final=True))
    assert fallback not in outer.call_args.args[0]["results"]


def test_set_query_does_not_treat_g_as_a_keyword_without_shortcuts(mocker: MockerFixture) -> None:
    core = UlauncherCore()
    launcher = LauncherMode()
    mocker.patch("ulauncher.core.get_modes", return_value=[launcher])
    mocker.patch.object(launcher, "handle_query")
    core.set_query("g firefox", MagicMock())
    assert isinstance(core._mode, LauncherMode)
    assert core.query.keyword is None
    assert str(core.query) == "g firefox"


def test_set_query_does_not_let_stock_web_shortcuts_steal_goshos_search(mocker: MockerFixture) -> None:
    class ShortcutMode:
        def matches_query_str(self, _query_str: str) -> bool:
            return False

    core = UlauncherCore()
    launcher = LauncherMode()
    shortcut_mode = ShortcutMode()
    mocker.patch("ulauncher.core.get_modes", return_value=[launcher, shortcut_mode])
    mocker.patch.object(launcher, "handle_query")
    # the seeded Google shortcut: goshos puts the web last unless you type `@`
    core._keyword_cache[shortcut_mode]["g"] = KeywordTrigger(  # type: ignore[index]
        name="Google Search", keyword="g", id="googlesearch", cmd="https://google.com/search?q=%s"
    )
    core.set_query("g firefox", MagicMock())
    assert isinstance(core._mode, LauncherMode)
    assert core.query.keyword is None
    assert str(core.query) == "g firefox"


def test_set_query_runs_a_user_shortcut_or_extension_keyword(mocker: MockerFixture) -> None:
    """Skipping ShortcutMode/ExtensionMode wholesale disabled every extension and user shortcut.

    Only the stock web shortcuts need to stay out of the way, and Shortcuts.load() already
    deletes those, so the keyword a user or an extension actually registered has to win.
    """

    class ShortcutMode:
        def matches_query_str(self, _query_str: str) -> bool:
            return False

        def handle_query(self, _query: Query, _callback: object) -> None:
            return

    class ExtensionMode(ShortcutMode):
        pass

    for mode_cls, keyword, trigger in (
        (
            ShortcutMode,
            "gh",
            KeywordTrigger(name="GitHub", keyword="gh", id="gh", cmd="https://github.com/search?q=%s"),
        ),
        (ExtensionMode, "tm", KeywordTrigger(name="Timer", keyword="tm")),
    ):
        core = UlauncherCore()
        launcher = LauncherMode()
        mode = mode_cls()
        mocker.patch("ulauncher.core.get_modes", return_value=[launcher, mode])
        mocker.patch.object(launcher, "handle_query")
        core._keyword_cache[mode][keyword] = trigger  # type: ignore[index]
        core.set_query(f"{keyword} something", MagicMock())
        assert core._mode is mode
        assert core.query.keyword == keyword
        assert core.query.argument == "something"

    # a bare keyword with no argument is still ordinary goshos search
    core = UlauncherCore()
    launcher = LauncherMode()
    mode = ShortcutMode()
    mocker.patch("ulauncher.core.get_modes", return_value=[launcher, mode])
    mocker.patch.object(launcher, "handle_query")
    core._keyword_cache[mode]["gh"] = KeywordTrigger(name="GitHub", keyword="gh")  # type: ignore[index]
    core.set_query("gh", MagicMock())
    assert isinstance(core._mode, LauncherMode)


def test_launcher_paint_skips_legacy_merge_for_keyword_queries(mocker: MockerFixture) -> None:
    class ShortcutMode:
        pass

    core = UlauncherCore()
    launcher = LauncherMode()
    core._mode = launcher
    core.query = Query("g", "foo")
    trigger = KeywordTrigger(name="Google", keyword="g")
    core._trigger_cache[ShortcutMode()] = [trigger]  # type: ignore[index]
    mocker.patch.object(core, "load_triggers")

    outer = MagicMock()
    row = LauncherResult(name="Firefox", kind="app")
    core._mode_callback(launcher, outer)(effects.render_results([row], final=True))
    assert outer.call_args.args[0]["results"] == [row]
