from __future__ import annotations

from ulauncher.modes.launcher.urls import FILE_EXTS, match_url

# Exact denylist from spotlight-goshos urlMatch.js (Version 2026.08.20).
GOSHOS_FILE_EXTS = frozenset(
    {
        "md",
        "py",
        "rs",
        "ts",
        "js",
        "jsx",
        "tsx",
        "c",
        "h",
        "go",
        "rb",
        "php",
        "java",
        "kt",
        "css",
        "html",
        "htm",
        "xml",
        "json",
        "yml",
        "yaml",
        "toml",
        "txt",
        "log",
        "conf",
        "ini",
        "cfg",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "webp",
        "ico",
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "zip",
        "tar",
        "gz",
        "mp3",
        "mp4",
        "wav",
        "exe",
        "deb",
        "rpm",
        "so",
        "dll",
        "vue",
        "sql",
        "db",
        "lock",
        "map",
        "wasm",
        "dart",
        "swift",
        "lua",
        "zig",
        "desktop",
        "service",
        "timer",
        "sh",
        "bash",
        "zsh",
        "fish",
        "ps1",
        "bat",
        "env",
        "mjs",
        "cjs",
        "mts",
        "cts",
        "scss",
        "sass",
        "csv",
        "tsv",
        "rst",
        "tex",
        "hs",
        "avif",
        "heic",
        "webm",
        "mkv",
        "mov",
        "iso",
        "apk",
    }
)


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
    assert FILE_EXTS == GOSHOS_FILE_EXTS
    assert len(FILE_EXTS) == 88


def test_real_domains_match() -> None:
    hit = match_url("example.com")
    assert hit is not None
    assert hit["url"].startswith("https://")
    assert hit["icon"] == "web-browser-symbolic"
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
    assert davs["icon"] == "network-server-symbolic"
    share = match_url("file://nas/Public Share")
    assert share is not None
    assert " " not in share["url"]
    assert share["kind"] == "file"


def test_mailto_magnet_localhost_and_https_with_space() -> None:
    mail = match_url("mailto:nin@example.com")
    assert mail is not None
    assert mail["url"] == "mailto:nin@example.com"
    assert mail["description"] == "Write email"
    magnet = match_url("magnet:?xt=urn:btih:abc")
    assert magnet is not None
    assert magnet["url"].startswith("magnet:")
    local = match_url("localhost:3000")
    assert local is not None
    assert local["url"] == "http://localhost:3000"
    loopback = match_url("127.0.0.1")
    assert loopback is not None
    assert loopback["url"] == "http://127.0.0.1"
    assert match_url("https://example.com/foo bar") is None
    assert match_url("999.999.999.999") is None
    assert match_url("localhostx") is None
    assert match_url("magnet:?xt=urn:btih:abc") is not None
    assert match_url("magnet:xt=urn:btih:abc") is not None
