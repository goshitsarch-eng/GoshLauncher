from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any, Callable

from ulauncher.utils import scheduling

logger = logging.getLogger(__name__)

_MAX_SCALAR_REPR = 120
_READ_CHUNK = 65536


def _summarize_dict(a: dict[str, Any]) -> str:
    fields = [f"{k}={a[k]!r}" for k in ("type", "name", "ext_id") if k in a]
    fields.extend(f"{k}=[{len(v)} items]" for k, v in a.items() if isinstance(v, list))
    return "{" + ", ".join(fields) + "}"


def summarize_ipc_args(args: Any) -> str:
    """Compact representation of IPC message args for logging"""
    parts = []
    for a in args:
        if isinstance(a, dict):
            parts.append(_summarize_dict(a))
        else:
            r = repr(a)
            parts.append(r if len(r) <= _MAX_SCALAR_REPR else r[: _MAX_SCALAR_REPR - 3] + "...")
    return "(" + ", ".join(parts) + ")"


class SocketMsgController:
    """
    Takes a file descriptor from a socket pair and provides read and write methods for
    newline-delimited JSON messages. Reading is asynchronous via the process's main loop
    (Qt in the app, MiniLoop in extension processes); writing is a plain blocking write,
    matching the old Gio.DataOutputStream behavior.
    """

    file_descriptor: int
    _on_close: Callable[[], None] | None

    def __init__(self, file_descriptor: int, on_close: Callable[[], None] | None = None) -> None:
        self.file_descriptor = file_descriptor
        self._on_close = on_close
        self._read_buffer = b""
        self._watch: scheduling.Context | None = None
        self._closed = False

    def _trigger_close(self) -> None:
        """
        Trigger the on_close callback if set, ensuring it's only called once.
        """
        callback = self._on_close
        self._on_close = None
        if callback:
            callback()

    def close(self) -> None:
        """
        Close the socket and cleanup resources.
        """
        if self._watch:
            self._watch.cancel()
            self._watch = None
        if not self._closed:
            self._closed = True
            with contextlib.suppress(OSError):
                os.close(self.file_descriptor)
        self._trigger_close()

    def send(self, data: Any) -> None:
        """
        Serialize data to JSON and send it to the socket.
        """
        try:
            json_str = json.dumps(data)
        except (TypeError, ValueError, RecursionError) as e:
            logger.warning("Data not JSON serializable %s", e)
            return

        payload = (json_str + "\n").encode()
        try:
            while payload:
                written = os.write(self.file_descriptor, payload)
                payload = payload[written:]
        except OSError as e:
            logger.warning("Failed to send message, connection likely closed: %s", e)
            self._trigger_close()

    def listen(self, on_message: Callable[[Any], None]) -> None:
        """
        Listen to and deserialize JSON messages from the socket.

        Args:
            on_message: Called with each successfully parsed message

        Invalid JSON messages are logged and skipped (should not happen if both sides use this class).
        Automatically continues reading until the connection is closed.
        """
        self._watch = scheduling.watch_fd(self.file_descriptor, self._read_available, on_message)

    def _read_available(self, on_message: Callable[[Any], None]) -> None:
        try:
            chunk = os.read(self.file_descriptor, _READ_CHUNK)
        except BlockingIOError:
            return
        except OSError:
            # I/O error - connection is broken
            self._trigger_close()
            return

        if not chunk:
            # Connection closed normally
            self._trigger_close()
            return

        self._read_buffer += chunk
        while b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received: %s", line.decode(errors="replace"))
                continue
            on_message(message)
