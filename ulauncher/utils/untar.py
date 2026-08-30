from __future__ import annotations

import os
import tarfile
from pathlib import Path, PurePosixPath
from shutil import rmtree

UNSAFE_PATH = "Unsafe archive path"
UNSUPPORTED_SPECIAL_FILE = "Unsupported archive special file"


def is_relative_to(child_path: str | os.PathLike[str], root_path: str | os.PathLike[str]) -> bool:
    """Return whether child_path resolves below root_path (Python 3.8 compatible)."""
    return Path(root_path).resolve() in Path(child_path).resolve().parents


def _safe_member_name(name: str, strip: int) -> str:
    """Apply strip-components while rejecting archive paths that can leave the target."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(UNSAFE_PATH, name)

    stripped = name.split("/", strip)[-1]
    if not stripped or stripped == ".":
        return stripped
    if not is_relative_to(stripped, "."):
        raise ValueError(UNSAFE_PATH, name)
    return stripped


def untar(archive_path: str, output_path: str, overwrite: bool = True, strip: int = 0) -> None:
    with tarfile.open(archive_path, mode="r") as archive:
        for member in archive.getmembers():
            # Links can redirect a later, otherwise-safe member outside output_path. Extension
            # archives are source trees and do not need links or special device nodes.
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValueError(UNSUPPORTED_SPECIAL_FILE, member.name)
            member.name = _safe_member_name(member.name, strip)
            if member.name and not is_relative_to(Path(output_path, member.name), output_path):
                raise ValueError(UNSAFE_PATH, member.name)

        if overwrite and os.path.exists(output_path):
            rmtree(output_path)
        archive.extractall(output_path)  # noqa: S202 -- every member is validated above
