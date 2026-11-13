"""Catalog persistence and readiness boundary."""

import duckdb
import pytest
from pydantic import ValidationError

from deterministic.catalog import Catalog, Project


def test_only_completed_ingestion_survives_as_selectable(tmp_path):
    path = tmp_path / "projects.duckdb"
    ready = Project(
        project_id="ready-id",
        source="fixture",
        revision="abc123",
        language="python",
        cache_path="/cache/ready",
        status="ready",
    )
    partial = Project(
        project_id="partial-id",
        source="fixture2",
        revision="def456",
        language="typescript",
        cache_path="/cache/partial",
        status="ingesting",
    )

    with Catalog(path) as catalog:
        catalog.upsert_project(ready)
        catalog.upsert_project(partial)

    with Catalog(path) as catalog:
        assert catalog.list_ready_projects() == [ready]


def test_project_rejects_invalid_boundary_values():
    with pytest.raises(ValidationError):
        Project(
            project_id="",
            source="fixture",
            revision="abc123",
            language="ruby",
            cache_path="/cache",
            status="ready",
        )


def test_catalog_validates_persisted_rows_before_returning_them(tmp_path):
    path = tmp_path / "projects.duckdb"
    with Catalog(path) as catalog:
        catalog._connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            ["bad", "fixture", "abc123", "ruby", "/cache", "ready", 1],
        )
    with Catalog(path) as catalog, pytest.raises(ValidationError):
        catalog.list_ready_projects()


def test_existing_catalog_receives_schema_version(tmp_path):
    path = tmp_path / "projects.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
                project_id VARCHAR PRIMARY KEY,
                source VARCHAR,
                revision VARCHAR,
                language VARCHAR,
                cache_path VARCHAR,
                status VARCHAR
            )
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)",
            ["old", "fixture", "abc123", "python", "/cache", "ready"],
        )

    with Catalog(path) as catalog:
        assert catalog.list_ready_projects()[0].schema_version == 1
