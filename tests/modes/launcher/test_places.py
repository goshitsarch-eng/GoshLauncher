from __future__ import annotations

from ulauncher.modes.launcher.places import (
    PLACE_CATALOG,
    match_places,
    place_matches,
    place_path,
    search_places,
)
from ulauncher.modes.launcher.plan import strip_leading_verb


def test_single_letter_is_prefix_only() -> None:
    assert not place_matches("Home", ["home", "~"], "o")
    assert place_matches("Desktop", ["desktop"], "d")
    assert place_matches("Documents", ["documents", "docs"], "d")
    assert not any(place["id"] == "home" for place in match_places("o"))
    assert not place_matches("Pictures", ["photos", "images"], "hot")


def test_place_icons_are_symbolic() -> None:
    from ulauncher.modes.launcher.places import PLACE_CATALOG

    assert PLACE_CATALOG[0]["icon"] == "user-home-symbolic"
    assert len(PLACE_CATALOG) == 9
    assert all(str(place["icon"]).endswith("-symbolic") for place in PLACE_CATALOG)


def test_spoken_open_documents() -> None:
    query = strip_leading_verb("open my documents")
    assert query == "documents"
    titles = [place["title"] for place in match_places(query)]
    assert "Documents" in titles
    folder = strip_leading_verb("open the pictures folder")
    assert folder == "pictures"
    directory = strip_leading_verb("open pictures dir")
    assert directory == "pictures"
    assert "Pictures" in [place["title"] for place in match_places(directory)]


def test_match_places_dedupes_shared_home_path() -> None:
    dirs = {
        "HOME": "/tmp/h",
        "XDG_DESKTOP_DIR": "/tmp/h",
        "XDG_DOCUMENTS_DIR": "/tmp/h",
        "XDG_DOWNLOAD_DIR": "/tmp/h",
    }
    hits = match_places("d", dirs=dirs)
    paths = [hit["path"] for hit in hits]
    assert paths == ["/tmp/h"]


def test_place_path_keeps_missing_xdg_dir() -> None:
    dirs = {"HOME": "/tmp/gosh-home-fake"}
    docs = next(place for place in PLACE_CATALOG if place["id"] == "documents")
    assert place_path(docs, dirs) == "/tmp/gosh-home-fake/Documents"
    home = next(place for place in PLACE_CATALOG if place["id"] == "home")
    assert place_path(home, dirs) == "/tmp/gosh-home-fake"
    mapped = {"HOME": "/tmp/gosh-home-fake", "XDG_DOCUMENTS_DIR": "/mnt/docs"}
    assert place_path(docs, mapped) == "/mnt/docs"


def test_search_places_description_icon_and_terminal_kind() -> None:
    dirs = {
        "HOME": "/home/me",
        "XDG_DOCUMENTS_DIR": "/home/me/Documents",
        "XDG_DOWNLOAD_DIR": "/home/me/Downloads",
    }
    none = search_places("docs", home="/home/me", dirs=dirs, find_in_path=lambda _name: None)
    assert none
    assert none[0]["title"] == "Documents"
    assert none[0]["description"] == "~/Documents"
    assert none[0]["icon"] == "folder-documents-symbolic"
    assert none[0]["kind"] == "place"
    assert all(not row["in_terminal"] for row in none)
    rows = search_places(
        "docs",
        home="/home/me",
        dirs=dirs,
        find_in_path=lambda name: name if name == "xdg-terminal-exec" else None,
    )
    assert [row["kind"] for row in rows] == ["place", "place"]
    assert rows[1]["title"] == "Open in Terminal"
    assert rows[1]["in_terminal"] is True
    assert rows[1]["description"] == "~/Documents"
    capped = search_places(
        "d",
        limit=1,
        home="/home/me",
        dirs=dirs,
        find_in_path=lambda name: name if name == "xdg-terminal-exec" else None,
    )
    assert len(capped) == 1
    assert capped[0]["title"] != "Open in Terminal"
