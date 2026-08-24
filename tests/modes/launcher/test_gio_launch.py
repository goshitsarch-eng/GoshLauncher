from __future__ import annotations

from pathlib import Path

import pytest

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
