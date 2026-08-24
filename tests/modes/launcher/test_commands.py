from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.modes.launcher.commands import (
    EXTRA_PATH_DIRS,
    command_file_is_ready,
    command_is_ready,
    command_needs_async,
    command_row_meta,
    command_uses_path_lookup,
    ensure_command,
    extra_path_dirs,
    find_user_program,
    first_command_arg,
    flush_command_lookup,
    invalidate_command_lookup,
    join_path_dirs,
    parse_command_argv,
    resolve_command_row,
    search_command,
)


def test_extra_path_dirs_follow_goshos_order() -> None:
    suffixes = [path.as_posix() for path in EXTRA_PATH_DIRS]
    assert suffixes[-1] == "/var/lib/flatpak/exports/bin"
    assert suffixes[0].endswith("/.local/bin")
    assert suffixes[1].endswith("/.local/share/flatpak/exports/bin")
    assert suffixes[2].endswith("/.cargo/bin")
    assert suffixes[3].endswith("/go/bin")
    assert suffixes[4].endswith("/bin")
    assert extra_path_dirs("/home/u") == [
        "/home/u/.local/bin",
        "/home/u/.local/share/flatpak/exports/bin",
        "/home/u/.cargo/bin",
        "/home/u/go/bin",
        "/home/u/bin",
        "/var/lib/flatpak/exports/bin",
    ]
    assert extra_path_dirs() == ["/var/lib/flatpak/exports/bin"]
    assert join_path_dirs(["/home/u/bin"], "/usr/bin") == "/home/u/bin:/usr/bin"
    dirs = extra_path_dirs("/home/u")
    assert find_user_program("tool", lambda _name: None, lambda path: path == "/home/u/go/bin/tool", dirs) == (
        "/home/u/go/bin/tool"
    )
    assert find_user_program("ls", lambda _name: "/bin/ls", lambda _path: False, dirs) == "/bin/ls"
    assert find_user_program("", lambda _name: "/bin/ls", lambda _path: True, dirs) is None


def test_command_row_meta_states() -> None:
    checking = command_row_meta("ls", ready=False, checking=True)
    assert checking["description"] == "Checking command"
    assert checking["ready"] is False
    missing = command_row_meta("nope", ready=False)
    assert missing["description"] == "Command not found"
    assert missing["icon"] == "dialog-warning-symbolic"
    assert checking["icon"] == "utilities-terminal-symbolic"
    ready = command_row_meta("ls", ready=True)
    assert ready["description"] == "Run command"
    assert ready["icon"] == "utilities-terminal-symbolic"
    assert ready["ready"] is True
    assert checking["activatable"] is False
    assert checking["type"] == "command"
    assert checking["id"] == "command:ls"
    assert missing["activatable"] is False
    assert missing["id"] == "command:nope"
    assert "activatable" not in ready
    assert first_command_arg([]) == ""
    assert first_command_arg(["ls", "-la"]) == "ls"
    assert command_uses_path_lookup("ls") is True
    assert command_uses_path_lookup("/bin/ls") is False
    assert command_uses_path_lookup("./tool") is False
    assert command_is_ready("ls", lambda name: "/bin/ls" if name == "ls" else None, lambda _path: False) is True
    assert command_is_ready("nope", lambda _name: None, lambda _path: False) is False
    assert command_is_ready("/bin/ls", lambda _name: None, lambda path: path == "/bin/ls") is True
    assert command_is_ready("/no/such", lambda _name: "/bin/true", lambda _path: False) is False
    assert command_file_is_ready(False, True) is True
    assert command_file_is_ready(True, True) is False
    assert command_file_is_ready(False, False) is False


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
