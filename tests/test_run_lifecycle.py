"""A builder exception must leave both arms visible to evaluation."""

import json
from pathlib import Path

from deterministic.catalog import Catalog, Project
from deterministic.cli import _migrate
from deterministic.ingestion.cache import ingest_evidence
from deterministic.telemetry.evaluator import evaluate


def test_builder_failure_is_durable_in_both_arms(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DETERMINISTIC_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("FALKORDB_HOST", raising=False)
    source = Path(__file__).parents[1] / "fixtures" / "python"
    ingest_evidence(source, "failure-case", tmp_path / "cache")
    with Catalog(tmp_path / "catalog" / "projects.duckdb") as catalog:
        catalog.upsert_project(
            Project(
                project_id="case",
                source=str(source),
                revision="failure-case",
                language="python",
                cache_path=str(source),
                status="ready",
            )
        )

    def fail(*_args):
        raise RuntimeError("injected builder failure")

    monkeypatch.setattr("deterministic.cli.run_workflow", fail)
    assert _migrate("case", "typescript", "both") == 1
    with Catalog(tmp_path / "catalog" / "projects.duckdb") as catalog:
        runs = catalog.list_runs()
    assert len(runs) == 2 and all(run["status"] == "failed" for run in runs)
    for run in runs:
        path = Path(run["run_path"])
        assert json.loads((path / "manifest.json").read_text())["status"] == "failed"
        assert "injected builder failure" in (path / "validation.json").read_text()
        assert "run_failed" in (path / "metrics.jsonl").read_text()
    report = evaluate(runs, tmp_path / "evaluation")
    assert len(report["pairs"]) == 1
    assert report["success_rate_by_memory"] == {"vector": 0.0, "graph": 0.0}
