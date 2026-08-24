from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher.commands import (
    command_needs_async,
    command_row_meta,
    ensure_command,
    flush_command_lookup,
    invalidate_command_lookup,
    parse_command_argv,
    resolve_command_row,
    search_command,
)


def test_command_row_meta_states() -> None:
    checking = command_row_meta("ls", ready=False, checking=True)
    assert checking["description"] == "Checking command"
    assert checking["ready"] is False
    missing = command_row_meta("nope", ready=False)
    assert missing["description"] == "Command not found"
    assert missing["icon"] == "dialog-warning"
    ready = command_row_meta("ls", ready=True)
    assert ready["description"] == "Run command"
    assert ready["ready"] is True


def test_parse_command_argv_expands_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    argv = parse_command_argv("~/bin/tool --flag")
    assert argv is not None
    assert argv[0] == str(tmp_path / "bin" / "tool")
    assert argv[1] == "--flag"
    later = parse_command_argv("ls ~/notes.txt")
    assert later is not None
    assert later[1] == str(tmp_path / "notes.txt")
    relative = parse_command_argv("scripts/deploy")
    assert relative is not None
    assert relative[0] == str(tmp_path / "scripts" / "deploy")


def test_resolve_command_row_sets_home_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    python = Path("/usr/bin/python3")
    if not python.is_file():
        python = Path("/usr/bin/true")
    if not python.is_file():
        return
    row = resolve_command_row(f"{python} --version")
    assert row is not None
    assert row["cwd"] == str(tmp_path)


def test_resolve_command_row_not_found() -> None:
    row = resolve_command_row("definitely-not-a-ulauncher-binary-xyz")
    assert row is not None
    assert row["ready"] is False
    assert row["description"] == "Command not found"
    assert row["argv"] == []


def test_search_command_path_lookup_is_sync() -> None:
    rows = search_command("definitely-not-a-ulauncher-binary-xyz")
    assert rows
    assert rows[0]["description"] == "Command not found"
    assert rows[0]["checking"] is False
    assert command_needs_async("ls") is False


def test_search_command_slash_path_pending_then_flush() -> None:
    binary = "/usr/bin/true" if Path("/usr/bin/true").is_file() else "/usr/bin/python3"
    if not Path(binary).is_file():
        return
    invalidate_command_lookup()
    rows = search_command(binary)
    assert rows[0]["description"] == "Checking command"
    assert command_needs_async(binary) is True
    ensure_command(binary, lambda: None)
    flush_command_lookup()
    resolved = search_command(binary)
    assert resolved[0]["description"] == "Run command"
    assert resolved[0]["ready"] is True


def test_resolve_command_row_ready_for_existing_binary() -> None:
    python = Path("/usr/bin/python3")
    if not python.is_file():
        python = Path("/usr/bin/true")
    if not python.is_file():
        return
    row = resolve_command_row(f"{python} --version")
    assert row is not None
    assert row["ready"] is True
    assert row["argv"][0] == str(python)
    assert row["description"] == "Run command"
