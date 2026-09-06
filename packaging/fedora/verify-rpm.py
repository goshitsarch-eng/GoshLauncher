#!/usr/bin/env python3
# ruff: noqa: PLR0912
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

EXPECTED_FILES = {
    "/usr/bin/ulauncher",
    "/usr/bin/ulauncher-toggle",
    "/usr/lib/systemd/user/ulauncher.service",
    "/usr/share/applications/com.goshapps.GoshLauncher.desktop",
    "/usr/share/dbus-1/services/com.goshapps.GoshLauncher.service",
    "/usr/share/icons/hicolor/scalable/apps/com.goshapps.GoshLauncher.svg",
    "/usr/share/icons/hicolor/scalable/status/ulauncher-indicator-symbolic-dark.svg",
    "/usr/share/icons/hicolor/scalable/status/ulauncher-indicator-symbolic.svg",
    "/usr/share/licenses/ulauncher/AUTHORS",
    "/usr/share/licenses/ulauncher/LICENSE",
    "/usr/share/licenses/ulauncher/copyright",
    "/usr/share/man/man1/ulauncher.1.gz",
    "/usr/share/metainfo/com.goshapps.GoshLauncher.metainfo.xml",
}
EXPECTED_REQUIRES = {
    "python3-pyside6",
    "python3-xlib",
    "kf6-kirigami",
    "kf6-qqc2-desktop-style",
    "qt6-qtdeclarative",
    "xdg-utils",
    "python3-pip",
}
ALLOWED_TREES = (
    re.compile(r"/usr/lib/python3\.\d+/site-packages/ulauncher(?:/.*)?"),
    re.compile(r"/usr/lib/python3\.\d+/site-packages/ulauncher-6\.0\.2\.dist-info(?:/.*)?"),
    re.compile(r"/usr/share/ulauncher(?:/.*)?"),
)
FORBIDDEN = (
    "flatpak-spawn",
    "org.freedesktop.flatpak",
    "goshlauncher-safe-host",
    "host_bridge",
    "host-bridge",
)
EXPECTED_ARGUMENT_COUNT = 2


def rpm(*args: str) -> str:
    return subprocess.check_output(("rpm", *args), text=True).strip()


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def path_is_allowed(path: str) -> bool:
    return path in EXPECTED_FILES or any(pattern.fullmatch(path) for pattern in ALLOWED_TREES)


def find_forbidden_payload(root: Path) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes().lower()
        relative = path.relative_to(root).as_posix()
        for token in FORBIDDEN:
            if token.encode() in content:
                findings.setdefault(token, []).append(relative)
    return findings


def inspect_payload_bytes(rpm_path: str) -> dict[str, list[str]]:
    for tool in ("rpm2cpio", "cpio"):
        if shutil.which(tool) is None:
            fail(f"Required payload inspection tool not found: {tool}")
    with tempfile.TemporaryDirectory(prefix="goshlauncher-rpm-") as directory:
        producer = subprocess.Popen(
            ("rpm2cpio", rpm_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        payload_stream = producer.stdout
        if payload_stream is None:
            producer.kill()
            fail("rpm2cpio did not provide a payload stream")
        consumer = subprocess.run(
            ("cpio", "-idm", "--quiet", "--no-absolute-filenames"),
            cwd=directory,
            stdin=payload_stream,
            capture_output=True,
            check=False,
        )
        payload_stream.close()
        producer_error = producer.stderr.read().decode(errors="replace") if producer.stderr else ""
        producer_status = producer.wait()
        if producer_status or consumer.returncode:
            fail(
                "Could not extract RPM payload for inspection: "
                f"rpm2cpio={producer_status} cpio={consumer.returncode} "
                f"{producer_error}{consumer.stderr.decode(errors='replace')}"
            )
        return find_forbidden_payload(Path(directory))


def main() -> None:  # noqa: PLR0915
    if len(sys.argv) != EXPECTED_ARGUMENT_COUNT:
        fail(f"Usage: {Path(sys.argv[0]).name} RPM")
    rpm_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(rpm_path):
        fail(f"RPM not found: {rpm_path}")

    metadata = rpm(
        "-qp",
        "--qf",
        "%{NAME}\n%{VERSION}\n%{RELEASE}\n%{ARCH}\n%{VENDOR}\n%{LICENSE}\n",
        rpm_path,
    ).splitlines()
    expected_metadata = ("goshlauncher", "6.0.2", "1.fc44", "noarch", "Gosh")
    if tuple(metadata[:5]) != expected_metadata or metadata[5] != "GPL-3.0-or-later AND LGPL-3.0-only":
        fail(f"Unexpected metadata: {metadata!r}")

    requires = set(rpm("-qp", "--requires", rpm_path).splitlines())
    missing_requires = {name for name in EXPECTED_REQUIRES if not any(line.startswith(name) for line in requires)}
    if missing_requires:
        fail(f"Missing runtime requirements: {sorted(missing_requires)}")

    files = set(rpm("-qpl", rpm_path).splitlines())
    missing_files = EXPECTED_FILES - files
    if missing_files:
        fail(f"Missing payload files: {sorted(missing_files)}")
    unexpected_files = sorted(path for path in files if not path_is_allowed(path))
    if unexpected_files:
        fail(f"Unexpected payload files: {unexpected_files}")

    inspected_text = "\n".join((*requires, *files)).lower()
    present_forbidden = [token for token in FORBIDDEN if token in inspected_text]
    if present_forbidden:
        fail(f"Forbidden host-bridge surface in RPM: {present_forbidden}")

    mode_rows = rpm("-qp", "--qf", "[%{FILEMODES:octal} %{FILENAMES}\n]", rpm_path).splitlines()
    privileged = []
    writable = []
    links = []
    for row in mode_rows:
        mode, path = row.split(" ", 1)
        mode_value = int(mode, 8)
        if mode_value & 0o6000:
            privileged.append(f"{mode} {path}")
        if mode_value & 0o002:
            writable.append(f"{mode} {path}")
        if stat.S_ISLNK(mode_value):
            links.append(f"{mode} {path}")
    if privileged:
        fail(f"RPM must not contain setuid/setgid files: {privileged}")
    if writable:
        fail(f"RPM must not contain world-writable paths: {writable}")
    if links:
        fail(f"RPM must not contain symbolic links: {links}")

    forbidden_payload = inspect_payload_bytes(rpm_path)
    if forbidden_payload:
        fail(f"Forbidden host-bridge content in extracted RPM payload: {forbidden_payload}")

    scripts = rpm("-qp", "--scripts", rpm_path)
    if scripts:
        fail(f"RPM must not contain scriptlets:\n{scripts}")

    filecaps = rpm("-qp", "--qf", "[%{FILECAPS}\n]", rpm_path).splitlines()
    if any(value and value != "(none)" for value in filecaps):
        fail(f"RPM must not contain file capabilities: {filecaps}")

    verification = rpm("-Kv", rpm_path)
    if "Signature" in verification:
        fail(f"Expected an unsigned RPM:\n{verification}")

    report = [
        f"verified={rpm_path}",
        f"nevra={metadata[0]}-{metadata[1]}-{metadata[2]}.{metadata[3]}",
        f"files={len(files)}",
        f"requires={len(requires)}",
        "scriptlets=none",
        "filecaps=none",
        "setuid_setgid=none",
        "world_writable=none",
        "symlinks=none",
        "forbidden_payload=none",
        "signature=unsigned",
    ]
    sys.stdout.write("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
