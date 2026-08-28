import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from ulauncher.utils import dbus


class TestDbusTriggerEvent:
    def test_sends_the_message_synchronously(self, mocker: MockerFixture) -> None:
        # A synchronous call is what guarantees the message reaches the bus before a
        # short-lived CLI process exits.
        mocker.patch("ulauncher.utils.dbus.check_app_running", return_value=True)
        bus = MagicMock()
        mocker.patch("ulauncher.utils.dbus._session_bus", return_value=bus)

        dbus.dbus_trigger_event("extensions:stop_preview")

        bus.call.assert_called_once()
        message = bus.call.call_args.args[0]
        payload = json.loads(message.arguments()[0])
        assert payload == {"name": "extensions:stop_preview", "args": []}

    def test_does_nothing_when_app_is_not_running(self, mocker: MockerFixture) -> None:
        mocker.patch("ulauncher.utils.dbus.check_app_running", return_value=False)
        bus = MagicMock()
        mocker.patch("ulauncher.utils.dbus._session_bus", return_value=bus)

        dbus.dbus_trigger_event("extensions:stop_preview")

        bus.call.assert_not_called()
