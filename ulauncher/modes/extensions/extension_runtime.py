from __future__ import annotations

import contextlib
import logging
import os
import signal
import socket
import subprocess
from collections import deque
from time import time
from typing import Callable, cast
from weakref import WeakSet

from ulauncher.internals import ipc, log_wire
from ulauncher.modes.extensions.extension_record import ExtensionExitCause
from ulauncher.utils import scheduling
from ulauncher.utils.socket_msg_controller import SocketMsgController

DEBUGPY_HOST = "127.0.0.1"
DEBUGPY_PORT = 5678
_EXIT_POLL_SEC = 0.1

ExitHandlerCallback = Callable[[ExtensionExitCause, str], None]
MessageHandlerCallback = Callable[[ipc.ExtensionMessage], None]
logger = logging.getLogger(__name__)


aborted_subprocesses: WeakSet[subprocess.Popen] = WeakSet()


class ExtensionRuntime:
    _ext_id: str
    _subprocess: subprocess.Popen
    _start_time: float
    _msg_controller: SocketMsgController
    _parent_socket: socket.socket | None = None
    _recent_errors: deque[str]
    _exit_handler: ExitHandlerCallback | None
    _message_handler: MessageHandlerCallback | None

    def __init__(
        self,
        ext_id: str,
        cmd: list[str],
        env: dict[str, str] | None = None,
        exit_handler: ExitHandlerCallback | None = None,
        message_handler: MessageHandlerCallback | None = None,
    ) -> None:
        self._ext_id = ext_id
        self._exit_handler = exit_handler
        self._message_handler = message_handler
        self._recent_errors = deque(maxlen=1)
        self._start_time = time()
        self._exit_handled = False
        self._exit_poll: scheduling.Context | None = None
        self._output_watches: dict[str, scheduling.Context] = {}
        self._output_buffers: dict[str, bytes] = {"stdout": b"", "stderr": b""}
        self._streams_open = 0

        extension_env = dict(os.environ)
        if env:
            extension_env.update(env)
        extension_env["ULAUNCHER_EXTENSION_ID"] = ext_id
        # Python block-buffers stdout when it isn't a terminal, holding back `print` output
        extension_env["PYTHONUNBUFFERED"] = "1"

        def socket_cleanup() -> None:
            if self._parent_socket:
                # The SocketMsgController owns (and already closed) the fd; detach so the
                # socket object doesn't close a possibly-reused fd number again.
                with contextlib.suppress(OSError):
                    self._parent_socket.detach()
                self._parent_socket = None
                logger.info("Extension %s connection closed", self._ext_id)
            self._schedule_exit_check()

        child_fd = -1
        try:
            # Create both parent and child sockets. The child fd number survives exec thanks
            # to pass_fds; SOCKETPAIR_FD tells the extension process which fd it is.
            self._parent_socket, child_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            child_fd = child_socket.detach()
            extension_env["SOCKETPAIR_FD"] = str(child_fd)

            self._subprocess = subprocess.Popen(
                cmd,
                env=extension_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(child_fd,),
                close_fds=True,
            )

            # Socket handler for parent process
            self._msg_controller = SocketMsgController(self._parent_socket.fileno(), socket_cleanup)
        except (OSError, TypeError):
            if self._parent_socket:
                with contextlib.suppress(OSError):
                    self._parent_socket.close()
                self._parent_socket = None
            raise
        finally:
            if child_fd >= 0:
                with contextlib.suppress(OSError):
                    os.close(child_fd)

        logger.debug("Launched %s using subprocess", self._ext_id)
        if self._subprocess.stdout is None or self._subprocess.stderr is None:
            err_msg = "Subprocess must be created with stdout/stderr pipes"
            raise AssertionError(err_msg)
        self._pipes = {"stdout": self._subprocess.stdout, "stderr": self._subprocess.stderr}
        for name, pipe in self._pipes.items():
            os.set_blocking(pipe.fileno(), False)
            self._streams_open += 1
            self._output_watches[name] = scheduling.watch_fd(pipe.fileno(), self._read_output, name)
        self._msg_controller.listen(self.handle_message)

    def stop(self) -> None:
        """
        Terminates extension
        """
        if self._subprocess.poll() is not None:
            logger.info("Cannot stop '%s'. It has already been terminated, or was never started", self._ext_id)
            return

        logger.info('Terminating extension "%s"', self._ext_id)
        aborted_subprocesses.add(self._subprocess)

        self._msg_controller.close()
        # wait for graceful shutdown before forcibly killing
        scheduling.timer(0.5, self._kill)

    def _kill(self) -> None:
        if self._subprocess.poll() is None:
            logger.info("Sending SIGKILL to extension %s", self._ext_id)
            with contextlib.suppress(ProcessLookupError):
                self._subprocess.send_signal(signal.SIGKILL)

    def send_message(self, message: ipc.Event, request_id: int | None = None) -> None:
        self._msg_controller.send([message, request_id])
        logger.debug("Sent message to %s: %s (request_id=%s)", self._ext_id, message, request_id)

    def handle_message(self, message: object) -> None:
        # message is a ipc.ExtensionMessage that has gone through the IPC json layer,
        # converting Results to dicts. ExtensionMode.handle_message rehydrates it
        if not isinstance(message, dict) or "name" not in message:
            logger.warning("Extension %s sent invalid message format: %s", self._ext_id, message)
            return
        if self._message_handler:
            self._message_handler(cast("ipc.ExtensionMessage", message))

    def _read_output(self, stream_name: str) -> None:
        pipe = self._pipes[stream_name]
        try:
            chunk = os.read(pipe.fileno(), 65536)
        except BlockingIOError:
            return
        except OSError:
            logger.exception("Failed to read %s line for %s", stream_name, self._ext_id)
            self._end_stream(stream_name)
            return

        if not chunk:
            # EOF: flush any unterminated final line, then track stream end
            remainder = self._output_buffers[stream_name]
            self._output_buffers[stream_name] = b""
            if remainder:
                self._emit_line(remainder, stream_name)
            self._end_stream(stream_name)
            return

        self._output_buffers[stream_name] += chunk
        while b"\n" in self._output_buffers[stream_name]:
            line, self._output_buffers[stream_name] = self._output_buffers[stream_name].split(b"\n", 1)
            if line:
                self._emit_line(line, stream_name)

    def _emit_line(self, line: bytes, stream_name: str) -> None:
        message = self.emit_output(line.decode("utf-8", errors="replace"), stream_name)
        if message and stream_name == "stderr":
            self._recent_errors.append(message)

    def _end_stream(self, stream_name: str) -> None:
        watch = self._output_watches.pop(stream_name, None)
        if watch:
            watch.cancel()
        self._streams_open = max(self._streams_open - 1, 0)
        if self._streams_open == 0:
            self._schedule_exit_check()

    def emit_output(self, output: str, stream_name: str) -> str:
        """Re-emit what the extension wrote through the app's handlers. Returns the message."""
        record = log_wire.parse(output)
        if record:
            # Sub-loggers of the extension's own logger are already namespaced
            if not (record.name == self._ext_id or record.name.startswith(f"{self._ext_id}.")):
                record.name = f"{self._ext_id}.{record.name}"
        else:
            # Unformatted stderr is a traceback or warning, and has to clear the app's WARNING level
            level = logging.WARNING if stream_name == "stderr" else logging.INFO
            record = logging.LogRecord(self._ext_id, level, "", 0, output, None, None, func=stream_name)
        logging.getLogger(record.name).handle(record)
        return record.getMessage()

    def _schedule_exit_check(self) -> None:
        """Wait (without blocking) for the process to actually exit, then report it once."""
        if self._exit_handled or self._exit_poll is not None:
            return
        self._exit_poll = scheduling.interval(_EXIT_POLL_SEC, self._poll_exit)
        self._poll_exit()

    def _poll_exit(self) -> None:
        if self._exit_handled:
            return
        if self._subprocess.poll() is None:
            return
        if self._exit_poll is not None:
            self._exit_poll.cancel()
            self._exit_poll = None
        self._exit_handled = True
        self.handle_exit()

    def handle_exit(self) -> None:
        self._msg_controller.close()

        if self._subprocess in aborted_subprocesses:
            if self._exit_handler:
                self._exit_handler("Stopped", "Extension was stopped by the user")
            logger.info('Extension "%s" was stopped by the user', self._ext_id)

        elif self._exit_handler:
            uptime_seconds = time() - self._start_time
            exit_status = self._subprocess.returncode
            error_msg = "\n".join(self._recent_errors)
            if "ModuleNotFoundError" in error_msg:
                package_name = error_msg.split("'")[1].split(".")[0]
                if package_name == "ulauncher":
                    self._exit_handler("MissingInternals", error_msg)
                    return
                if package_name:
                    self._exit_handler("MissingModule", package_name)
                    return
            if uptime_seconds < 1:
                logger.error('Extension "%s" terminated before it could start', self._ext_id)
                self._exit_handler("Terminated", error_msg)
                return

            if not error_msg:
                error_msg = f'Extension "{self._ext_id}" exited with code {exit_status} after {uptime_seconds} seconds.'

            self._exit_handler("Exited", error_msg)
