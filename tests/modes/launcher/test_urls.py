from __future__ import annotations

from ulauncher.modes.launcher.urls import match_url


def test_file_extensions_are_not_urls() -> None:
    assert match_url("node.js") is None
    assert match_url("readme.md") is None
    assert match_url("main.py") is None
    assert match_url("package.json") is None
    assert match_url("photo.png") is None
    assert match_url("app.mjs") is None
    assert match_url("data.csv") is None
    assert match_url("style.scss") is None
    assert match_url("readme.md.") is None


def test_real_domains_match() -> None:
    hit = match_url("example.com")
    assert hit is not None
    assert hit["url"].startswith("https://")
    assert match_url("https://ulauncher.io") is not None


def test_javascript_scheme_is_rejected() -> None:
    assert match_url("javascript:alert(1)") is None
    assert match_url("vbscript:alert(1)") is None
    assert match_url("java\u200bscript:alert(1)") is None
    assert match_url("data:text/html,hi") is None


def test_trailing_fqdn_dot_and_private_hosts() -> None:
    hit = match_url("example.com.")
    assert hit is not None
    assert hit["url"] == "https://example.com"
    lan = match_url("printer.lan")
    assert lan is not None
    assert lan["url"] == "http://printer.lan"
    loopback = match_url("::1")
    assert loopback is not None
    assert loopback["url"] == "http://[::1]"
    public_ip = match_url("8.8.8.8")
    assert public_ip is not None
    assert public_ip["url"] == "http://8.8.8.8"


def test_davs_and_spaced_file_share() -> None:
    davs = match_url("davs://nas/share")
    assert davs is not None
    assert davs["url"] == "davs://nas/share"
    assert davs["description"] == "Open location"
    share = match_url("file://nas/Public Share")
    assert share is not None
    assert " " not in share["url"]
    assert share["kind"] == "file"
