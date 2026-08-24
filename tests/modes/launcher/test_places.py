from __future__ import annotations

from ulauncher.modes.launcher.places import match_places, place_matches
from ulauncher.modes.launcher.plan import strip_leading_verb


def test_single_letter_is_prefix_only() -> None:
    assert not place_matches("Home", ["home", "~"], "o")
    assert place_matches("Desktop", ["desktop"], "d")
    assert place_matches("Documents", ["documents", "docs"], "d")
    assert not any(place["id"] == "home" for place in match_places("o"))


def test_place_icons_are_symbolic() -> None:
    from ulauncher.modes.launcher.places import PLACE_CATALOG

    assert PLACE_CATALOG[0]["icon"] == "user-home-symbolic"
    assert all(str(place["icon"]).endswith("-symbolic") for place in PLACE_CATALOG)


def test_spoken_open_documents() -> None:
    query = strip_leading_verb("open my documents")
    assert query == "documents"
    titles = [place["title"] for place in match_places(query)]
    assert "Documents" in titles
    folder = strip_leading_verb("open the pictures folder")
    assert folder == "pictures"
