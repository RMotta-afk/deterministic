"""Catalog persistence and readiness boundary."""

from deterministic.catalog import Catalog, Project


def test_only_completed_ingestion_survives_as_selectable(tmp_path):
    path = tmp_path / "projects.duckdb"
    ready = Project("ready-id", "fixture", "abc123", "python", "/cache/ready", "ready")
    partial = Project("partial-id", "fixture2", "def456", "typescript", "/cache/partial", "ingesting")

    with Catalog(path) as catalog:
        catalog.upsert_project(ready)
        catalog.upsert_project(partial)

    with Catalog(path) as catalog:
        assert catalog.list_ready_projects() == [ready]
