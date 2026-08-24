from __future__ import annotations

import ipaddress
import re
from typing import Optional
from urllib.parse import quote

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_BARE_DOMAIN = re.compile(
    r"^(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?#].*)?$",
    re.IGNORECASE,
)
_HOST_PORT = re.compile(r"^([a-z0-9.-]+):(\d{1,5})(?:[/].*)?$", re.IGNORECASE)
_LOCALHOST = re.compile(r"^localhost(?::\d{1,5})?(?:[/].*)?$", re.IGNORECASE)
_MDNS = re.compile(r"^[a-z0-9-]+\.local(?::\d{1,5})?(?:[/].*)?$", re.IGNORECASE)
_FILE_RE = re.compile(r"^file:", re.IGNORECASE)

BLOCKED_SCHEMES = frozenset({"javascript", "data", "vbscript"})
LOCAL_SCHEMES = frozenset({"http", "https", "sftp", "smb", "ftp", "file", "mailto", "magnet"})
# Last labels that are almost always files, not sites (node.js, readme.md).
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


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _is_local_host(host: str) -> bool:
    h = host.lower().strip("[]")
    if h in ("localhost", "127.0.0.1", "::1") or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return False


def match_url(query: str) -> Optional[dict]:
    raw = query.strip()
    if not raw or (" " in raw.split("://", 1)[-1] and not raw.lower().startswith("file:")):
        # spaces only allowed in file URIs (encoded below)
        if " " in raw and not raw.lower().startswith("file:"):
            return None

    lowered = raw.lower()
    if lowered.startswith("javascript:") or lowered.startswith("data:"):
        return None

    if _FILE_RE.match(raw):
        # encode spaces in file URIs
        encoded = quote(raw, safe=":/")
        return {"url": encoded, "kind": "file", "label": raw}

    if lowered.startswith(("mailto:", "magnet:", "sftp://", "smb://", "ftp://", "https://", "http://")):
        return {"url": raw, "kind": "scheme", "label": raw}

    if _LOCALHOST.match(raw) or _MDNS.match(raw):
        url = raw if "://" in raw else f"http://{raw}"
        return {"url": url, "kind": "local", "label": raw}

    # IPv4 / bracketed IPv6 with optional port
    host_for_ip = raw.split("/")[0].split("?")[0]
    if host_for_ip.startswith("[") or _is_ip(host_for_ip.split(":")[0]):
        host = host_for_ip.split(":")[0] if not host_for_ip.startswith("[") else host_for_ip.split("]")[0] + "]"
        scheme = "http" if _is_local_host(host.strip("[]")) else "https"
        url = raw if "://" in raw else f"{scheme}://{raw}"
        return {"url": url, "kind": "ip", "label": raw}

    host_for_tld = raw.split("/")[0].split("?")[0].split("#")[0]
    if host_for_tld.startswith("www."):
        host_for_tld = host_for_tld[4:]
    tld = host_for_tld.rsplit(".", 1)[-1].lower() if "." in host_for_tld else ""
    if tld in FILE_EXTS:
        return None

    if _BARE_DOMAIN.match(raw) or lowered.startswith("www."):
        url = raw if "://" in raw else f"https://{raw}"
        return {"url": url, "kind": "domain", "label": raw}

    hp = _HOST_PORT.match(raw)
    if hp and not _SCHEME_RE.match(raw):
        host, port = hp.group(1), int(hp.group(2))
        if 1 <= port <= 65535:
            scheme = "http" if _is_local_host(host) else "https"
            return {"url": f"{scheme}://{raw}", "kind": "hostport", "label": raw}

    # IPv6 without brackets: 2001:db8::1 — too ambiguous with host:port; skip unless bracketed
    return None
