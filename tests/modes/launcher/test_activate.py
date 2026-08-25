from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.activate import (
    activatable_result,
    activate_popup_result,
    activate_result_safe,
    indexed_activatable_result,
    result_can_activate,
)


def test_enter_on_pending_uses_first_ready_sibling() -> None:
    pending = SimpleNamespace(actions={})
    ready = SimpleNamespace(actions={"activate": {"name": "Activate"}})
    later = SimpleNamespace(actions={"activate": {"name": "Activate"}})
    assert result_can_activate(pending) is False
    assert result_can_activate(ready) is True
    assert activatable_result([pending, ready, later], 0) is ready
    assert activatable_result([pending, ready, later], 1) is ready
    assert indexed_activatable_result([pending, ready, later], 0) is None
    assert indexed_activatable_result([pending, ready, later], 1) is ready


def test_activate_result_safe_swallows_errors() -> None:
    assert activate_result_safe({"activate": lambda: None}) is True

    def boom() -> None:
        message = "vanished"
        raise RuntimeError(message)

    assert activate_result_safe({"activate": boom}) is False
    assert result_can_activate({"activate": lambda: None}) is True
    assert result_can_activate({"activate": lambda: None, "activatable": False}) is False
    from ulauncher.modes.launcher.commands import command_row_meta

    assert result_can_activate(command_row_meta("ls", ready=False, checking=True)) is False


def test_activate_popup_result_closes_then_runs() -> None:
    order: list[str] = []

    def close() -> None:
        order.append("close")

    def activate(_result: object, alt: bool) -> None:
        order.append(f"activate:{alt}")

    assert activate_popup_result({"activate": lambda: None}, close, activate) is True
    assert order == ["close", "activate:False"]


def test_activate_popup_result_skips_close_on_alt() -> None:
    order: list[str] = []
    assert (
        activate_popup_result(
            {"activate": lambda: None},
            lambda: order.append("close"),
            lambda _result, alt: order.append(f"activate:{alt}"),
            alt=True,
        )
        is True
    )
    assert order == ["activate:True"]


def test_activate_popup_result_swallows_vanished_target() -> None:
    closed = False

    def close() -> None:
        nonlocal closed
        closed = True

    def boom(_result: object, _alt: bool) -> None:
        message = "gone"
        raise RuntimeError(message)

    assert activate_popup_result({"activate": lambda: None}, close, boom) is False
    assert closed is True


def test_activate_popup_result_skips_pending_without_close() -> None:
    order: list[str] = []
    pending = SimpleNamespace(actions={}, activatable=False)
    assert (
        activate_popup_result(
            pending,
            lambda: order.append("close"),
            lambda *_args: order.append("activate"),
        )
        is False
    )
    assert order == []
