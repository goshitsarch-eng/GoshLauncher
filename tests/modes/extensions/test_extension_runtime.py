import logging
import signal
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture

from ulauncher.internals import log_wire
from ulauncher.modes.extensions.extension_runtime import ExtensionRuntime, aborted_subprocesses


class TestExtensionRuntime:
    @pytest.fixture(autouse=True)
    def popen(self, mocker: MockerFixture) -> MagicMock:
        popen_class = mocker.patch("ulauncher.modes.extensions.extension_runtime.subprocess.Popen")
        proc = popen_class.return_value
        proc.poll.return_value = None
        proc.stdout = Mock()
        proc.stdout.fileno.return_value = 11
        proc.stderr = Mock()
        proc.stderr.fileno.return_value = 12
        return popen_class

    @pytest.fixture(autouse=True)
    def message_socket(self, mocker: MockerFixture) -> MagicMock:
        mock_parent_sock = Mock()
        mock_child_sock = Mock()
        mock_child_sock.detach.return_value = 13
        mock_parent_sock.fileno.return_value = 14
        return mocker.patch(
            "ulauncher.modes.extensions.extension_runtime.socket.socketpair",
            return_value=(mock_parent_sock, mock_child_sock),
        )

    @pytest.fixture(autouse=True)
    def message_socket_class(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("ulauncher.modes.extensions.extension_runtime.SocketMsgController")

    @pytest.fixture(autouse=True)
    def os_module(self, mocker: MockerFixture) -> MagicMock:
        os_mock = mocker.patch("ulauncher.modes.extensions.extension_runtime.os")
        os_mock.environ = {}
        return os_mock

    @pytest.fixture(autouse=True)
    def watch_fd(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("ulauncher.modes.extensions.extension_runtime.scheduling.watch_fd")

    @pytest.fixture
    def time(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("ulauncher.modes.extensions.extension_runtime.time")

    @pytest.fixture
    def mock_timer(self, mocker: MockerFixture) -> MagicMock:
        """Mock the timer utility function used for scheduling delayed kills."""
        return mocker.patch("ulauncher.modes.extensions.extension_runtime.scheduling.timer")

    def test_run__basic_execution__is_called(self, popen: MagicMock, watch_fd: MagicMock) -> None:
        extid = "mock.test_run__basic_execution__is_called"

        ExtensionRuntime(extid, ["mock/path/to/ext"])

        popen.assert_called_once()
        # both stdout and stderr get an fd watch
        assert watch_fd.call_count == 2

    def test_read_output__stderr__records_recent_errors(self, os_module: MagicMock) -> None:
        extid = "mock.test_read_output__stderr__records_recent_errors"

        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])

        os_module.read.return_value = b"Test Output 1\n"
        runtime._read_output("stderr")
        assert runtime._recent_errors[0] == "Test Output 1"

        os_module.read.return_value = b"Test Output 2\n"
        runtime._read_output("stderr")
        # The latest line should replace the previous line
        assert runtime._recent_errors[0] == "Test Output 2"

    def test_read_stdout_line__is_not_treated_as_an_error(self, os_module: MagicMock) -> None:
        extid = "mock.test_read_stdout_line__is_not_treated_as_an_error"

        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])
        os_module.read.return_value = b"printed to stdout\n"
        runtime._read_output("stdout")

        assert not runtime._recent_errors

    def test_emit_output__wire_encoded__restores_the_extensions_record(self, caplog: LogCaptureFixture) -> None:
        extid = "mock.test_emit_output"
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])
        line = log_wire.WireFormatter().format(
            logging.LogRecord(extid, logging.WARNING, "/ext/main.py", 42, "line one\nline two", None, None, func="run")
        )

        with caplog.at_level(logging.DEBUG):
            message = runtime.emit_output(line, "stderr")

        assert message == "line one\nline two"
        record = caplog.records[-1]
        assert (record.name, record.levelno, record.funcName, record.lineno) == (extid, logging.WARNING, "run", 42)

    def test_emit_output__extensions_own_logger__is_nested_under_the_ext_id(self, caplog: LogCaptureFixture) -> None:
        extid = "mock.test_emit_output_nested"
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])
        line = log_wire.WireFormatter().format(
            logging.LogRecord("__main__", logging.INFO, "/ext/main.py", 1, "hi", None, None, func="run")
        )

        with caplog.at_level(logging.DEBUG):
            runtime.emit_output(line, "stdout")

        assert caplog.records[-1].name == f"{extid}.__main__"

    def test_emit_output__extensions_sub_logger__keeps_its_name(self, caplog: LogCaptureFixture) -> None:
        extid = "mock.test_emit_output_sub_logger"
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])
        line = log_wire.WireFormatter().format(
            logging.LogRecord(f"{extid}.sub", logging.INFO, "/ext/main.py", 1, "hi", None, None, func="run")
        )

        with caplog.at_level(logging.DEBUG):
            runtime.emit_output(line, "stdout")

        assert caplog.records[-1].name == f"{extid}.sub"

    def test_handle_exit__signaled(self) -> None:
        extid = "mock.test_handle_exit__signaled"
        exit_handler = Mock()

        runtime = ExtensionRuntime(extid, ["mock/path/to/ext"], None, exit_handler)
        aborted_subprocesses.add(runtime._subprocess)

        runtime.handle_exit()
        exit_handler.assert_called_once_with("Stopped", "Extension was stopped by the user")

    def test_handle_exit__rapid_exit(self, time: MagicMock) -> None:
        extid = "mock.test_handle_exit__rapid_exit"
        curtime = 100.0
        starttime = curtime - 0.5
        time.return_value = starttime
        exit_handler = Mock()

        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"], None, exit_handler)
        runtime._subprocess.returncode = 9
        time.return_value = curtime

        runtime.handle_exit()
        exit_handler.assert_called_once_with("Terminated", "")

    def test_handle_exit(self, time: MagicMock) -> None:
        extid = "mock.test_handle_exit"
        exit_handler = Mock()
        curtime = 100.0
        starttime = curtime - 5
        time.return_value = starttime

        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"], None, exit_handler)
        runtime._subprocess.returncode = 9
        time.return_value = curtime
        runtime.handle_exit()
        exit_handler.assert_called_once_with(
            "Exited", 'Extension "mock.test_handle_exit" exited with code 9 after 5.0 seconds.'
        )

    def test_stop(self, mock_timer: MagicMock) -> None:
        """Test that stop() closes the connection and schedules a kill timer."""
        extid = "mock.test_stop"
        exit_handler = Mock()
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"], None, exit_handler)

        runtime._subprocess.poll.return_value = None  # still running
        runtime._msg_controller = Mock()
        runtime.stop()

        runtime._msg_controller.close.assert_called_once()
        mock_timer.assert_called_once_with(0.5, runtime._kill)

    def test_kill__sends_sigkill(self) -> None:
        """Test that _kill() sends SIGKILL if the process is still running."""

        extid = "mock.test_kill__sends_sigkill"
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])

        runtime._subprocess.poll.return_value = None  # still running
        runtime._kill()

        runtime._subprocess.send_signal.assert_called_once_with(signal.SIGKILL)

    def test_kill__noop_when_already_reaped(self) -> None:
        """_kill() must not signal once the process has been reaped (poll() is set)."""
        extid = "mock.test_kill__noop_when_already_reaped"
        runtime: Any = ExtensionRuntime(extid, ["mock/path/to/ext"])

        runtime._subprocess.poll.return_value = 0
        runtime._kill()

        runtime._subprocess.send_signal.assert_not_called()
