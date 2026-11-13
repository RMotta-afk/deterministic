"""Persistent project catalog for a single CLI writer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class Project:
    project_id: str
    source: str
    revision: str
    language: str
    cache_path: str
    status: str


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
                status VARCHAR NOT NULL CHECK (status IN ('ingesting', 'ready', 'failed'))
            )
            """
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def upsert_project(self, project: Project) -> None:
        if project.status not in {"ingesting", "ready", "failed"}:
            raise ValueError(f"invalid project status: {project.status}")
        self._connection.execute(
            """
            INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (project_id) DO UPDATE SET
                source = excluded.source,
                revision = excluded.revision,
                language = excluded.language,
                cache_path = excluded.cache_path,
                status = excluded.status
            """,
            [
                project.project_id,
                project.source,
                project.revision,
                project.language,
                project.cache_path,
                project.status,
            ],
        )

    def list_ready_projects(self) -> list[Project]:
        rows = self._connection.execute(
            """
            SELECT project_id, source, revision, language, cache_path, status
            FROM projects WHERE status = 'ready'
            ORDER BY source, revision
            """
        ).fetchall()
        return [Project(*row) for row in rows]
