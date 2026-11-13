"""Validated backend benchmark boundaries for pinned submodules."""

import fnmatch
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BenchmarkScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_language: Literal["python", "typescript"]
    target_language: Literal["python", "typescript"]
    migration_roots: list[str] = Field(min_length=1)
    migration_exclude_globs: list[str]
    contract_roots: list[str]
    preserve_roots: list[str]
    connection: str = Field(min_length=1)

    @field_validator("migration_roots", "contract_roots", "preserve_roots")
    @classmethod
    def validate_roots(cls, roots: list[str]) -> list[str]:
        for root in roots:
            if not root or root.startswith("/") or "\\" in root or ".." in root.split("/"):
                raise ValueError(f"invalid repository-relative root: {root}")
        return roots

    def role_for(self, path: str) -> Literal["migrate", "contract"] | None:
        def within(root: str) -> bool:
            return path == root or path.startswith(root + "/")

        in_migration = any(within(root) for root in self.migration_roots)
        excluded = any(fnmatch.fnmatch(path, pattern) for pattern in self.migration_exclude_globs)
        if in_migration and not excluded:
            return "migrate"
        if excluded or any(within(root) for root in self.contract_roots):
            return "contract"
        return None

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class ScopeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    repositories: list[BenchmarkScope] = Field(min_length=1)


def load_scope(path: Path, profile: str) -> BenchmarkScope:
    manifest = ScopeManifest.model_validate_json(path.read_text(encoding="utf-8"))
    found = [scope for scope in manifest.repositories if scope.id == profile]
    if len(found) != 1:
        raise ValueError(f"expected exactly one benchmark profile named {profile}")
    return found[0]
