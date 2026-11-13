"""Load an immutable local or Git source snapshot into the shared cache."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EXCLUDED_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}


class SourceSnapshot(BaseModel):
    """Validated reference to an immutable source cache entry."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    path: Path
    schema_version: Literal[1] = 1


def _copy_source(source: Path, target: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        root = Path(directory)
        return {name for name in names if name in EXCLUDED_DIRS or (root / name).is_symlink()}

    shutil.copytree(source, target, ignore=ignore)


def _content_revision(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def load_source(source: str, cache_root: Path) -> SourceSnapshot:
    """Copy a source to a content-addressed cache path and return its revision."""
    local = Path(source).expanduser()
    cache_root.mkdir(parents=True, exist_ok=True)
    if local.is_dir() and cache_root.resolve().is_relative_to(local.resolve()):
        raise ValueError("cache directory must be outside the source directory")

    with tempfile.TemporaryDirectory(prefix=".staging-", dir=cache_root) as temporary:
        staging = Path(temporary) / "source"
        if local.is_dir():
            _copy_source(local.resolve(), staging)
        elif source.startswith("https://"):
            subprocess.run(
                ["git", "clone", "--depth", "1", "--", source, str(staging)],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            git_revision = subprocess.run(
                ["git", "-C", str(staging), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
            cleaned = Path(temporary) / "cleaned"
            _copy_source(staging, cleaned)
            staging = cleaned
        else:
            raise ValueError("source must be a local directory or HTTPS Git URL")

        content_hash = _content_revision(staging)
        revision = f"{git_revision}-{content_hash}" if not local.is_dir() else content_hash
        destination = cache_root / content_hash
        if not destination.exists():
            staging.rename(destination)
        return SourceSnapshot(source=source, revision=revision, path=destination)
