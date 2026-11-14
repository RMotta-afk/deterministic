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


class Run(BaseModel):
    """Validated run row at the DuckDB boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    run_id: str = Field(min_length=1)
    pair_id: str | None
    project_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    memory: Literal["vector", "graph"]
    status: Literal["running", "complete", "failed"]
    run_path: str = Field(min_length=1)
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
        self._connection.execute("""CREATE TABLE IF NOT EXISTS runs (
            run_id VARCHAR PRIMARY KEY, pair_id VARCHAR, project_id VARCHAR NOT NULL,
            revision VARCHAR NOT NULL, direction VARCHAR NOT NULL, memory VARCHAR NOT NULL,
            status VARCHAR NOT NULL, run_path VARCHAR NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 1
        )""")
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

    def record_run(self, run: dict[str, str | None]) -> None:
        run = Run.model_validate(run).model_dump()
        self._connection.execute(
            """INSERT OR REPLACE INTO runs
            (run_id,pair_id,project_id,revision,direction,memory,status,run_path)
            VALUES (?,?,?,?,?,?,?,?)""",
            [
                run[k]
                for k in (
                    "run_id",
                    "pair_id",
                    "project_id",
                    "revision",
                    "direction",
                    "memory",
                    "status",
                    "run_path",
                )
            ],
        )

    def list_runs(self) -> list[dict[str, str | None]]:
        cols = (
            "run_id",
            "pair_id",
            "project_id",
            "revision",
            "direction",
            "memory",
            "status",
            "run_path",
        )
        return [
            Run.model_validate(dict(zip(cols, row, strict=True))).model_dump(
                exclude={"schema_version"}
            )
            for row in self._connection.execute(
                "SELECT run_id,pair_id,project_id,revision,direction,memory,status,run_path "
                "FROM runs ORDER BY run_id"
            ).fetchall()
        ]
