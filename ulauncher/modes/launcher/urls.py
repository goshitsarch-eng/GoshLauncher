"""URL detection, ported from spotlight-goshos urlMatch.js."""

from __future__ import annotations

import re
from typing import Optional

from ulauncher.modes.launcher.paths import canonicalize_file_uri, canonicalize_remote_uri, path_from_file_uri

_SCHEME_RE = re.compile(r"^(https?://|sftp://|ftp://|smb://|davs?://|www\.|file://)\S+$", re.IGNORECASE)
_MAILTO_RE = re.compile(r"^mailto:[^\s@]+@[^\s]+$", re.IGNORECASE)
_MAGNET_RE = re.compile(r"^magnet:\S+$", re.IGNORECASE)
_LABEL = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_DOMAIN_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+(:\d{{1,5}})?([/?#]\S*)?$", re.IGNORECASE)
_LOCAL_RE = re.compile(r"^(localhost|127\.0\.0\.1)(:\d{1,5})?([/?#]\S*)?$", re.IGNORECASE)
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}(:\d{1,5})?([/?#]\S*)?$")
_IPV6_RE = re.compile(r"^\[([0-9a-f:.]+)\](:\d{1,5})?([/?#]\S*)?$", re.IGNORECASE)
_BARE_LOOPBACK_V6 = re.compile(r"^::1([/?#]\S*)?$")
_PRIVATE_SUFFIX_RE = re.compile(r"\.(local|lan|home|internal|home\.arpa)$", re.IGNORECASE)
# zero-width joiners, bidi controls, and NUL can hide a dangerous scheme
_SCHEME_FUZZ_RE = re.compile(r"[\0\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_URI_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*$", re.IGNORECASE)

UNSAFE_LAUNCH_SCHEMES = frozenset({"javascript", "data", "vbscript"})
# last labels that are almost always files, not sites — even vs country codes such as md/py
FILE_EXTS = frozenset(
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


def is_dotted_ipv4(host: str) -> bool:
    parts = host.split(".")
    if len(parts) != 4:
        return False
    return all(part.isdigit() and int(part) <= 255 for part in parts)


def is_plausible_web_host(host: str) -> bool:
    if not host:
        return False
    parts = [part for part in host.split(".") if part]
    if len(parts) < 2:
        return False
    tld = parts[-1].lower()
    if tld in FILE_EXTS:
        return False
    return bool(re.fullmatch(r"[a-z]{2,}", tld))


def launch_uri_scheme(query: str) -> str:
    cleaned = _SCHEME_FUZZ_RE.sub("", query).strip()
    colon = cleaned.find(":")
    if colon <= 0:
        return ""
    scheme = cleaned[:colon]
    if not _URI_SCHEME_RE.match(scheme):
        return ""
    return scheme.lower()


def is_unsafe_launch_uri(query: str) -> bool:
    return launch_uri_scheme(query) in UNSAFE_LAUNCH_SCHEMES


def strip_trailing_dots(text: str) -> str:
    return re.sub(r"\.+$", "", text)


def is_file_url_query(query: str) -> bool:
    if not query or not re.match(r"^file:", query, re.IGNORECASE):
        return False
    if path_from_file_uri(query):
        return True
    if re.match(r"^file:///\S*$", query, re.IGNORECASE):
        return True
    # file://host/share may contain spaces after the host
    return bool(re.match(r"^file://[^/\s?#]+(/.*)?$", query, re.IGNORECASE))


def is_remote_location_query(query: str) -> bool:
    if not query:
        return False
    return bool(re.match(r"^(sftp|ftp|smb|davs?)://[^/\s?#]+(/.*)?$", query, re.IGNORECASE))


def host_of_query(query: str) -> str:
    trimmed = query.strip()
    if _BARE_LOOPBACK_V6.match(trimmed):
        return "::1"
    without_scheme = re.sub(r"^(https?://|file://)", "", trimmed, flags=re.IGNORECASE)
    host_port = re.split(r"[/?#]", without_scheme, maxsplit=1)[0]
    if host_port[:1] == "[":
        end = host_port.find("]")
        if end > 1:
            return host_port[1:end]
        return ""
    return host_port.split(":")[0]


def scheme_for_host(host: str) -> str:
    if re.fullmatch(r"localhost", host, re.IGNORECASE):
        return "http"
    if is_dotted_ipv4(host):
        return "http"
    if ":" in host:
        return "http"
    if _PRIVATE_SUFFIX_RE.search(host):
        return "http"
    return "https"


def is_url_query(query: str) -> bool:
    trimmed = query.strip()
    if not trimmed:
        return False
    if is_unsafe_launch_uri(trimmed):
        return False
    if re.match(r"^file:", trimmed, re.IGNORECASE):
        return is_file_url_query(trimmed)
    if is_remote_location_query(trimmed):
        return True
    if re.search(r"\s", trimmed):
        return False
    if (
        _SCHEME_RE.match(trimmed)
        or _MAILTO_RE.match(trimmed)
        or _MAGNET_RE.match(trimmed)
        or _LOCAL_RE.match(trimmed)
        or _IPV6_RE.match(trimmed)
        or _BARE_LOOPBACK_V6.match(trimmed)
    ):
        return True
    host_query = strip_trailing_dots(trimmed)
    if _IPV4_RE.match(host_query):
        return is_dotted_ipv4(host_of_query(host_query))
    return bool(_DOMAIN_RE.match(host_query) and is_plausible_web_host(host_of_query(host_query)))


def normalize_url(query: str) -> Optional[str]:
    trimmed = query.strip()
    if is_unsafe_launch_uri(trimmed):
        return None
    if re.match(r"^https?://", trimmed, re.IGNORECASE):
        return strip_trailing_dots(trimmed)
    if re.match(r"^file:", trimmed, re.IGNORECASE):
        return canonicalize_file_uri(trimmed) if is_file_url_query(trimmed) else None
    if re.match(r"^(sftp://|ftp://|smb://|davs?://)", trimmed, re.IGNORECASE):
        return canonicalize_remote_uri(trimmed) if is_remote_location_query(trimmed) else None
    if re.match(r"^(mailto:|magnet:)", trimmed, re.IGNORECASE):
        return trimmed
    if re.match(r"^www\.", trimmed, re.IGNORECASE):
        return f"https://{strip_trailing_dots(trimmed)}"
    host_query = strip_trailing_dots(trimmed)
    host = host_of_query(host_query)
    if ":" in host and not host_query.startswith("["):
        rest = host_query[len(host) :] if host_query.startswith(host) else ""
        return f"{scheme_for_host(host)}://[{host}]{rest}"
    return f"{scheme_for_host(host)}://{host_query}"


def url_row_description(url: str) -> str:
    if url.startswith("mailto:"):
        return "Write email"
    if url.startswith("magnet:"):
        return "Open magnet link"
    if re.match(r"^(sftp|ftp|smb|davs?):", url, re.IGNORECASE):
        return "Open location"
    if url.lower().startswith("file:"):
        return "Open path" if path_from_file_uri(url) else "Open location"
    return "Open in browser"


def url_row_icon(url: str) -> str:
    if url.startswith("mailto:"):
        return "mail-message-new-symbolic"
    if re.match(r"^(sftp|ftp|smb|davs?):", url, re.IGNORECASE):
        return "network-server-symbolic"
    if url.lower().startswith("file:"):
        return "folder-symbolic" if path_from_file_uri(url) else "network-server-symbolic"
    return "web-browser-symbolic"


def match_url(query: str) -> Optional[dict]:
    raw = query.strip()
    if not is_url_query(raw):
        return None
    url = normalize_url(raw)
    if not url:
        return None
    if url.lower().startswith("file:"):
        kind = "file"
    elif re.match(r"^(sftp|ftp|smb|davs?):", url, re.IGNORECASE):
        kind = "remote"
    elif url.startswith(("mailto:", "magnet:")):
        kind = "scheme"
    elif (
        _LOCAL_RE.match(strip_trailing_dots(raw))
        or _BARE_LOOPBACK_V6.match(raw)
        or is_dotted_ipv4(host_of_query(strip_trailing_dots(raw)))
    ):
        kind = "local"
    else:
        kind = "domain"
    return {
        "url": url,
        "kind": kind,
        "label": url,
        "description": url_row_description(url),
        "icon": url_row_icon(url),
    }
