from __future__ import annotations

from ulauncher.modes.launcher.urls import match_url


def test_file_extensions_are_not_urls() -> None:
    assert match_url("node.js") is None
    assert match_url("readme.md") is None
    assert match_url("main.py") is None


def test_real_domains_match() -> None:
    hit = match_url("example.com")
    assert hit is not None
    assert hit["url"].startswith("https://")
    assert match_url("https://ulauncher.io") is not None


def test_javascript_scheme_is_rejected() -> None:
    assert match_url("javascript:alert(1)") is None
