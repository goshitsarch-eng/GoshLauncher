from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.utils.loop_helpers import drive_until
from ulauncher.utils.subprocess_utils import download_file, run_command


def test_run_command_success() -> None:
    result, error = drive_until(lambda ok, err: run_command([sys.executable, "-c", "print('hello')"], ok, err))
    assert error is None
    assert result.strip() == "hello"


def test_run_command_nonzero_exit() -> None:
    result, error = drive_until(lambda ok, err: run_command([sys.executable, "-c", "import sys; sys.exit(3)"], ok, err))
    assert result is None
    assert isinstance(error, subprocess.CalledProcessError)
    assert error.returncode == 3


def test_run_command_spawn_failure() -> None:
    result, error = drive_until(lambda ok, err: run_command(["definitely-not-a-real-binary-xyz"], ok, err))
    assert result is None
    assert isinstance(error, OSError)


def test_download_file_success(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload")
    dest = tmp_path / "out.txt"
    result, error = drive_until(lambda ok, err: download_file(src.as_uri(), str(dest), ok, err))
    assert error is None
    assert result == str(dest)
    assert dest.read_text() == "payload"


def test_download_file_failure(tmp_path: Path) -> None:
    dest = tmp_path / "out.txt"
    result, error = drive_until(lambda ok, err: download_file("file:///nonexistent/nope.txt", str(dest), ok, err))
    assert result is None
    assert error is not None
