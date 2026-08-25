from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher import gio_launch
from ulauncher.modes.launcher.gio_launch import find_in_user_path, open_uri, reset_program_path_cache, spawn_argv


def test_find_in_user_path_caches_hits_and_misses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_program_path_cache()
    tool = tmp_path / "tool"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o755)
    monkeypatch.setattr(
        "ulauncher.modes.launcher.gio_launch.extra_path_dirs",
        lambda _home=None: [str(tmp_path)],
    )
    monkeypatch.setattr("ulauncher.modes.launcher.gio_launch.which", lambda _name: None)
    assert find_in_user_path("tool") == str(tool)
    tool.unlink()
    assert find_in_user_path("tool") == str(tool)
    reset_program_path_cache()
    assert find_in_user_path("tool") is None
    assert find_in_user_path("tool") is None


def test_spawn_argv_resolves_path_and_prepends_user_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_program_path_cache()
    calls: list[tuple] = []

    def _spawn(argv: list[str], working_dir: str | None = None, extra_env: dict[str, str] | None = None) -> None:
        calls.append((argv, working_dir, extra_env))

    monkeypatch.setattr("ulauncher.modes.launcher.gio_launch.find_in_user_path", lambda name: f"/opt/{name}")
    monkeypatch.setattr(
        "ulauncher.modes.launcher.gio_launch.extra_path_dirs", lambda _home=None: ["/home/u/.local/bin"]
    )
    monkeypatch.setenv("HOME", "/home/u")
    monkeypatch.setenv("PATH", "/usr/bin")
    spawn_argv(["ls", "-la"], cwd=None, spawn=_spawn)
    argv, workdir, extra = calls[0]
    assert argv == ["/opt/ls", "-la"]
    assert workdir == "/home/u"
    assert extra is not None
    assert extra["PATH"].startswith("/home/u/.local/bin:")


def test_spawn_argv_skips_missing_path_command() -> None:
    reset_program_path_cache()
    calls: list[list[str]] = []
    spawn_argv(["definitely-missing-ulauncher-bin"], spawn=lambda argv, **_kwargs: calls.append(argv))
    assert calls == []


def test_open_uri_rejects_unsafe_and_canonicalizes_file() -> None:
    opened: list[str] = []
    open_uri("javascript:alert(1)", opener=opened.append)
    open_uri("\u200bdata:text/html,hi", opener=opened.append)
    open_uri("file:///home/u/My Documents", opener=opened.append)
    assert opened == ["file:///home/u/My%20Documents"]


def test_launch_uri_uses_gio_app_info() -> None:
    source = Path(gio_launch.__file__).read_text()
    assert "Gio.AppInfo.launch_default_for_uri_async" in source
    assert "Gio.AppLaunchContext()" in source
    assert "display.get_app_launch_context()" not in source


def test_prefs_saved_reprobes_program_path_and_parental(monkeypatch: pytest.MonkeyPatch) -> None:
    # Importing mode.py registers the goshos extension.disable() reset on the
    # daemon's reconfigure event (a settings save).
    import ulauncher.modes.launcher.mode  # noqa: F401
    from ulauncher.modes.launcher.parental import (
        has_parental_give_up,
        mark_parental_give_up,
        reset_parental_give_up,
    )
    from ulauncher.utils.eventbus import EventBus

    reset_program_path_cache()
    reset_parental_give_up()
    try:
        holder: dict[str, str | None] = {"found": None}
        monkeypatch.setattr(
            "ulauncher.modes.launcher.gio_launch.find_user_program",
            lambda _name, *_a, **_k: holder["found"],
        )
        # First lookup misses and the miss is cached for the session.
        assert find_in_user_path("goshterm") is None
        # The program is installed mid-session, but the cache still returns the miss.
        holder["found"] = "/usr/bin/goshterm"
        assert find_in_user_path("goshterm") is None
        mark_parental_give_up()
        assert has_parental_give_up() is True

        # A preferences save is the daemon's re-enable moment.
        EventBus().emit("app:prefs_saved", ("enable_calculator",))

        # PATH is re-probed and the parental give-up flag is cleared.
        assert find_in_user_path("goshterm") == "/usr/bin/goshterm"
        assert has_parental_give_up() is False
    finally:
        reset_program_path_cache()
        reset_parental_give_up()
