from __future__ import annotations

from types import SimpleNamespace

from ulauncher.modes.launcher.activate import activatable_result, indexed_activatable_result, result_can_activate


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
