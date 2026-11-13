"""Persistent project catalog for a single CLI writer."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    """Validated catalog record crossing the ingestion/CLI boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    project_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    language: Literal["pending", "python", "typescript"]
    cache_path: str = Field(min_length=1)
    status: Literal["ingesting", "ready", "failed"]
    schema_version: Literal[1] = 1


class Catalog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(path))
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,
                revision VARCHAR NOT NULL,
                language VARCHAR NOT NULL,
                cache_path VARCHAR NOT NULL,
                status VARCHAR NOT NULL CHECK (status IN ('ingesting', 'ready', 'failed')),
                schema_version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        columns = {
            row[1] for row in self._connection.execute("PRAGMA table_info('projects')").fetchall()
        }
        if "schema_version" not in columns:
            self._connection.execute(
                "ALTER TABLE projects ADD COLUMN schema_version INTEGER DEFAULT 1"
            )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def upsert_project(self, project: Project) -> None:
        self._connection.execute(
            """
            INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (project_id) DO UPDATE SET
                source = excluded.source,
                revision = excluded.revision,
                language = excluded.language,
                cache_path = excluded.cache_path,
                status = excluded.status,
                schema_version = excluded.schema_version
            """,
            [
                project.project_id,
                project.source,
                project.revision,
                project.language,
                project.cache_path,
                project.status,
                project.schema_version,
            ],
        )

    def list_ready_projects(self) -> list[Project]:
        rows = self._connection.execute(
            """
            SELECT project_id, source, revision, language, cache_path, status, schema_version
            FROM projects WHERE status = 'ready'
            ORDER BY source, revision
            """
        ).fetchall()
        columns = (
            "project_id",
            "source",
            "revision",
            "language",
            "cache_path",
            "status",
            "schema_version",
        )
        return [Project.model_validate(dict(zip(columns, row, strict=True))) for row in rows]
