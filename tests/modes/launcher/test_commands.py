from __future__ import annotations

from pathlib import Path

from ulauncher.modes.launcher.commands import command_row_meta, parse_command_argv, resolve_command_row


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


def test_parse_command_argv_expands_home(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    argv = parse_command_argv("~/bin/tool --flag")
    assert argv is not None
    assert argv[0] == str(tmp_path / "bin" / "tool")
    assert argv[1] == "--flag"


def test_resolve_command_row_not_found() -> None:
    row = resolve_command_row("definitely-not-a-ulauncher-binary-xyz")
    assert row is not None
    assert row["ready"] is False
    assert row["description"] == "Command not found"
    assert row["argv"] == []


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
