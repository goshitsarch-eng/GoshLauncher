from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from ulauncher.utils.untar import untar


def _write_file(archive: tarfile.TarFile, name: str, data: bytes = b"data") -> None:
    member = tarfile.TarInfo(name)
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def test_untar_extracts_regular_source_tree(tmp_path: Path) -> None:
    archive_path = tmp_path / "extension.tar"
    with tarfile.open(archive_path, "w") as archive:
        _write_file(archive, "project/manifest.json", b"{}")

    output = tmp_path / "output"
    untar(str(archive_path), str(output), strip=1)

    assert (output / "manifest.json").read_bytes() == b"{}"


def test_untar_rejects_parent_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "extension.tar"
    with tarfile.open(archive_path, "w") as archive:
        _write_file(archive, "../escaped")

    with pytest.raises(ValueError, match="Unsafe archive path"):
        untar(str(archive_path), str(tmp_path / "output"))
    assert not (tmp_path / "escaped").exists()


def test_untar_rejects_symlink_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "extension.tar"
    with tarfile.open(archive_path, "w") as archive:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../escape"
        archive.addfile(link)
        _write_file(archive, "link/pwned")

    escape = tmp_path / "escape"
    escape.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing").write_text("keep")
    with pytest.raises(ValueError, match="Unsupported archive special file"):
        untar(str(archive_path), str(output))
    assert not (escape / "pwned").exists()
    assert (output / "existing").read_text() == "keep"
