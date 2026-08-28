from __future__ import annotations

import contextlib
import logging
import os
import sys
from types import TracebackType

from ulauncher.cli import CLIArguments

_BOX_INNER = 77


def _boxed_warning(*lines: str) -> str:
    bar = "═" * _BOX_INNER
    body = "\n".join(f"║{line[:_BOX_INNER].center(_BOX_INNER)}║" for line in lines)
    return f"\n\n╔{bar}╗\n{body}\n╚{bar}╝\n\n"


def run(_: CLIArguments) -> int:
    from ulauncher import init_helpers

    init_helpers.init_x11_threads()

    from ulauncher import api_version, app_display_name, version
    from ulauncher.utils.environment import DESKTOP_NAME, DISTRO, IS_X11_COMPATIBLE, XDG_SESSION_TYPE
    from ulauncher.utils.migrate import v5_to_v6
    from ulauncher.utils.v5_killer import kill_ulauncher_v5

    logger = logging.getLogger(__name__)

    try:
        import PySide6
        from PySide6.QtCore import qVersion
    except ImportError:
        print(f"{app_display_name} requires PySide6 (Qt 6). Install it with your package manager or pip.")  # noqa: T201
        return 1

    def except_hook(exctype: type[BaseException], exception: BaseException, traceback: TracebackType | None) -> None:
        logger.error("Uncaught exception", exc_info=(exctype, exception, traceback))

    sys.excepthook = except_hook

    logger.info("Desktop: %s (%s) on %s", DESKTOP_NAME, XDG_SESSION_TYPE, DISTRO)
    if "-" in version:
        logger.warning(
            _boxed_warning(
                f"YOU ARE RUNNING A PRE-RELEASE of {app_display_name.upper()}.",
                "Please do not report extension API support warnings to extension developers",
                "We are still in the process of developing and documenting these features",
            )
        )

    logger.info("%s version %s", app_display_name, version)
    logger.info("Extension API version %s", api_version)
    logger.info("Qt %s (PySide6 %s)", qVersion(), PySide6.__version__)
    if XDG_SESSION_TYPE != "X11":
        logger.info("X11 backend: %s", ("Yes" if IS_X11_COMPATIBLE else "No"))

    # Ensure that Ulauncher v5 is not running
    # TODO: Remove this 4-6 months after v6 release
    # Import here because of the dependency on the logger setup
    kill_ulauncher_v5()

    # Migrate user data to v6 compatible
    v5_to_v6()

    from ulauncher.ui.app import UlauncherApp

    app = UlauncherApp()

    # Perf-test probe: when ULAUNCHER_PERF_START_BOOTTIME is set, schedule the launcher
    # to open as soon as the main loop is idle so the probe can measure cold-start to
    # first input. Without this, `ulauncher start` would register as a daemon and idle
    # until an external D-Bus call arrived.
    if os.environ.get("ULAUNCHER_PERF_START_BOOTTIME"):
        from ulauncher.utils import scheduling

        scheduling.run_when_idle(app.show_launcher)

    with contextlib.suppress(KeyboardInterrupt):
        return app.start(activate=False)

    return 0
