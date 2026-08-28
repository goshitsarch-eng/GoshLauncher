from __future__ import annotations

from pathlib import Path

import pytest

from ulauncher.utils import mime_apps


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake XDG world with one file manager registered for smb and directories."""
    config = tmp_path / "config"
    data = tmp_path / "data"
    apps = data / "applications"
    apps.mkdir(parents=True)
    config.mkdir()
    (apps / "org.example.files.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Example Files\nExec=examplefiles %U\nIcon=system-file-manager\n"
    )
    (config / "mimeapps.list").write_text(
        "[Default Applications]\ninode/directory=org.example.files.desktop\n"
        "x-scheme-handler/smb=org.example.files.desktop\n"
    )
    monkeypatch.setattr(mime_apps.paths, "XDG_CONFIG_HOME", str(config))
    monkeypatch.setattr(mime_apps.paths, "XDG_DATA_HOME", str(data))
    monkeypatch.setattr(mime_apps.paths, "XDG_DATA_DIRS", [str(data)])
    import ulauncher.utils.desktop_entry as desktop_entry

    monkeypatch.setattr(desktop_entry.paths, "XDG_DATA_HOME", str(data))
    monkeypatch.setattr(desktop_entry.paths, "XDG_DATA_DIRS", [str(data)])
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    return tmp_path


def test_default_app_for_scheme(xdg: Path) -> None:
    handler = mime_apps.default_app_for("x-scheme-handler/smb")
    assert handler is not None
    assert handler.get_id() == "org.example.files.desktop"


def test_handler_for_registered_scheme(xdg: Path) -> None:
    handler = mime_apps.handler_for_uri("smb://nas.local/media")
    assert handler is not None
    assert handler.get_display_name() == "Example Files"


def test_remote_scheme_falls_back_to_the_file_manager(xdg: Path) -> None:
    """An unregistered remote filesystem scheme must still open somewhere sensible:
    the default directory handler mounts the share itself. This is the network-share fix."""
    handler = mime_apps.handler_for_uri("sftp://user@host/srv")
    assert handler is not None
    assert handler.get_id() == "org.example.files.desktop"


def test_unknown_web_scheme_has_no_handler(xdg: Path) -> None:
    assert mime_apps.handler_for_uri("gemini://example.org") is None


def test_open_detached_launches_the_handler(xdg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils import launch_detached as launch_detached_mod

    spawned: list[list[str]] = []
    monkeypatch.setattr(launch_detached_mod, "launch_detached", lambda cmd, *a, **k: spawned.append(cmd))

    launch_detached_mod.open_detached("smb://nas.local/media")

    assert spawned == [["examplefiles", "smb://nas.local/media"]]


def test_open_detached_falls_back_to_xdg_open(xdg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ulauncher.utils import launch_detached as launch_detached_mod

    spawned: list[list[str]] = []
    monkeypatch.setattr(launch_detached_mod, "launch_detached", lambda cmd, *a, **k: spawned.append(cmd))

    launch_detached_mod.open_detached("gemini://example.org")

    assert spawned == [["xdg-open", "gemini://example.org"]]
