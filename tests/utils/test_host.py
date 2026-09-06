from __future__ import annotations

from pytest_mock import MockerFixture

from ulauncher.utils.host import find_program, host_argv
from ulauncher.utils.systemd_controller import SystemdController, SystemdUnitStatus


def test_native_argv_is_unchanged(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"FLATPAK_ID": ""})
    assert host_argv(["firefox", "https://example.com"]) == ["firefox", "https://example.com"]


def test_flatpak_uses_host_spawn_without_shell(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"FLATPAK_ID": "com.goshapps.GoshLauncher"})
    assert host_argv(["app", "/run/host/usr/share/applications/app.desktop", "two words"], "/home/user") == [
        "flatpak-spawn",
        "--host",
        "--directory=/home/user",
        "app",
        "/usr/share/applications/app.desktop",
        "two words",
    ]


def test_flatpak_program_lookup_uses_host_files(mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"FLATPAK_ID": "com.goshapps.GoshLauncher"})
    mocker.patch("os.path.isfile", side_effect=lambda path: path == "/run/host/usr/bin/konsole")
    mocker.patch("os.access", return_value=True)
    assert find_program("konsole") == "/usr/bin/konsole"
    assert find_program("missing-terminal") is None


def test_autostart_reports_failed_write(mocker: MockerFixture) -> None:
    import pytest

    mocker.patch.object(SystemdController, "status", return_value=SystemdUnitStatus(["CanStart=yes"]))
    mocker.patch("ulauncher.utils.systemd_controller.systemctl_run", return_value="")
    with pytest.raises(OSError, match="Could not change autostart state"):
        SystemdController("ulauncher").toggle(True)


def test_flatpak_command_resolves_host_executable(mocker: MockerFixture) -> None:
    from ulauncher.modes.launcher.commands import resolve_command_row

    mocker.patch.dict("os.environ", {"FLATPAK_ID": "com.goshapps.GoshLauncher"})
    mocker.patch("ulauncher.utils.host.find_program", return_value="/usr/bin/konsole")
    row = resolve_command_row("konsole --new-tab")
    assert row is not None
    assert row["ready"]
    assert row["argv"] == ["/usr/bin/konsole", "--new-tab"]
