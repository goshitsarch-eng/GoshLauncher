from unittest.mock import MagicMock

from ulauncher.utils.gsettings import schema_for_id, settings_or_none, settings_with_path_or_none

MISSING = "io.ulauncher.definitely.not.installed"


def test_missing_schema_is_none_instead_of_aborting() -> None:
    # Gio.Settings.new() on an unknown schema is a g_error, which kills the process instead of
    # raising, so these helpers must never reach it.
    assert schema_for_id(MISSING) is None
    assert settings_or_none(MISSING) is None
    assert settings_with_path_or_none(MISSING, "/io/ulauncher/nope/") is None


def test_installed_schema_is_opened() -> None:
    from ulauncher.gi import Gio

    # this one ships with GLib itself, so it is present wherever the tests can run
    schema_id = "org.gtk.Settings.FileChooser"
    if schema_for_id(schema_id) is None:
        return
    assert isinstance(settings_or_none(schema_id), Gio.Settings)


def test_no_default_schema_source_is_none(mocker: MagicMock) -> None:
    from ulauncher.gi import Gio

    mocker.patch.object(Gio.SettingsSchemaSource, "get_default", return_value=None)
    assert schema_for_id("org.gtk.Settings.FileChooser") is None
    assert settings_or_none("org.gtk.Settings.FileChooser") is None
