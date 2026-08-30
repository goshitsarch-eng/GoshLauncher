from pathlib import Path

import ulauncher

REPO_ROOT = Path(__file__).parents[1]
ABOUT_QML = REPO_ROOT / "ulauncher/ui/qml/PreferencesWindow.qml"
APP_ID = "com.goshapps.GoshLauncher"
USER_FACING_FILES = (
    ABOUT_QML,
    REPO_ROOT / "README.md",
    REPO_ROOT / f"{APP_ID}.desktop",
    REPO_ROOT / f"{APP_ID}.metainfo.xml",
)


def test_release_identity_and_version_are_synchronized() -> None:
    qml = ABOUT_QML.read_text()
    readme = (REPO_ROOT / "README.md").read_text()
    manpage = (REPO_ROOT / "ulauncher.1").read_text()
    metainfo = (REPO_ROOT / f"{APP_ID}.metainfo.xml").read_text()

    assert ulauncher.version == "6.0.0"
    assert 'text: "Made by Gosh"' in qml
    assert 'accessibleName: "Maker: Gosh"' in qml
    assert f"Current release: {ulauncher.version}" in readme
    assert ulauncher.version in manpage
    assert f'version="{ulauncher.version}"' in metainfo
    assert "6.0.0-beta37" not in f"{readme}\n{manpage}\n{metainfo}"


def test_user_facing_identity_has_no_personal_names() -> None:
    text = "\n".join(path.read_text() for path in USER_FACING_FILES).lower()
    assert "vaughan" not in text
    assert "jones" not in text
