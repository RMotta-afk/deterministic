"""Source snapshots remain stable after the input changes."""

from deterministic.catalog import Catalog
from deterministic.cli import main
from deterministic.ingestion.repo_loader import load_source


def test_local_snapshot_is_content_addressed_and_immutable(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("value = 1\n", encoding="utf-8")
    ignored = source / "node_modules"
    ignored.mkdir()
    (ignored / "generated.js").write_text("ignored", encoding="utf-8")
    cache = tmp_path / "cache"

    first = load_source(str(source), cache)
    assert (first.path / "main.py").read_text(encoding="utf-8") == "value = 1\n"
    assert not (first.path / "node_modules").exists()

    (source / "main.py").write_text("value = 2\n", encoding="utf-8")
    second = load_source(str(source), cache)
    assert first.revision != second.revision
    assert (first.path / "main.py").read_text(encoding="utf-8") == "value = 1\n"


def test_ingest_records_snapshot_as_incomplete_until_evidence_is_ready(tmp_path, monkeypatch):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "main.py").write_text("answer = 42\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DETERMINISTIC_DATA_DIR", str(data_dir))

    assert main(["ingest", str(source)]) == 2
    with Catalog(data_dir / "catalog" / "projects.duckdb") as catalog:
        assert catalog.list_ready_projects() == []
