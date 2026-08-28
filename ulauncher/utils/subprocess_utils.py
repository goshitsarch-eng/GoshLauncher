from __future__ import annotations

import subprocess
import sys
import threading
from typing import Callable

from ulauncher.utils import scheduling

OnSuccess = Callable[[str], None]
OnError = Callable[[Exception], None]  # receives an OSError or subprocess.CalledProcessError for non-zero exits


def run_command(cmd: list[str], on_success: OnSuccess, on_error: OnError, *, cwd: str | None = None) -> None:
    """Run a one-shot command without blocking the main loop, delivering its stdout to
    on_success or an error to on_error (both called on the main loop thread)."""

    def _worker() -> None:
        try:
            # A killed process is reported as a negative returncode by subprocess already.
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            scheduling.run_when_idle(on_error, error)
            return
        scheduling.run_when_idle(on_success, proc.stdout)

    threading.Thread(target=_worker, daemon=True, name="run_command").start()


# Run Python/urllib.request in a subprocess to avoid needing a dependency like curl or wget.
_DOWNLOAD_SCRIPT = (
    "import sys, urllib.request, shutil; "
    "shutil.copyfileobj(urllib.request.urlopen(sys.argv[1], timeout=30), open(sys.argv[2], 'wb'))"
)


def download_file(url: str, dest_path: str, on_success: OnSuccess, on_error: OnError) -> None:
    """Download url to dest_path without blocking. Calls on_success(dest_path) or on_error(error).
    See _DOWNLOAD_SCRIPT for why this spawns Python."""
    run_command(
        [sys.executable, "-c", _DOWNLOAD_SCRIPT, url, dest_path],
        lambda _stdout: on_success(dest_path),
        on_error,
    )
