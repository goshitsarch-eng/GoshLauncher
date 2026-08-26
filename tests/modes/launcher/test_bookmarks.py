def test_remote_bookmark_is_found_by_host() -> None:
    from ulauncher.modes.launcher.bookmarks import _described, match_bookmarks, parse_gtk_bookmarks

    rows = _described(parse_gtk_bookmarks("smb://server/share Share\nsftp://alice@nas.local/srv/data NAS Data\n"))
    # a remote row's description is the whole URI, and path_matches_query only matches at a word
    # start over " -_./", so the user@ prefix hid the hostname
    assert [row["title"] for row in match_bookmarks("nas", rows)] == ["NAS Data"]
    assert [row["title"] for row in match_bookmarks("nas.local", rows)] == ["NAS Data"]
    assert [row["title"] for row in match_bookmarks("server", rows)] == ["Share"]
    assert [row["title"] for row in match_bookmarks("nas data", rows)] == ["NAS Data"]
