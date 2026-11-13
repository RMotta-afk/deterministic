"""Source snapshots remain stable after the input changes."""

import subprocess

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


def test_git_snapshot_can_be_pinned_to_exact_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    source_file = repo / "main.py"
    source_file.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "main.py"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "first"], check=True, capture_output=True
    )
    pinned = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    cache = tmp_path / "cache"
    snapshot = load_source(repo.as_uri(), cache, pinned)
    assert snapshot.revision.startswith(pinned + "-")
    assert (snapshot.path / "main.py").read_text(encoding="utf-8") == "value = 1\n"


def test_ingest_records_ready_snapshot_after_evidence_is_built(tmp_path, monkeypatch):
    source = tmp_path / "fixture"
    source.mkdir()
    (source / "main.py").write_text("answer = 42\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DETERMINISTIC_DATA_DIR", str(data_dir))

    assert main(["ingest", str(source)]) == 0
    manifests = list((data_dir / "runs").glob("ingest-*/manifest.json"))
    assert len(manifests) == 1
    assert '"status": "ready"' in manifests[0].read_text(encoding="utf-8")
    with Catalog(data_dir / "catalog" / "projects.duckdb") as catalog:
        projects = catalog.list_ready_projects()
        assert len(projects) == 1
        assert projects[0].revision
        assert projects[0].language == "python"


def test_failed_ingest_keeps_a_manifest(tmp_path, monkeypatch):
    import pytest

    data_dir = tmp_path / "data"
    monkeypatch.setenv("DETERMINISTIC_DATA_DIR", str(data_dir))
    with pytest.raises(ValueError, match="source must be"):
        main(["ingest", str(tmp_path / "missing")])
    manifests = list((data_dir / "runs").glob("ingest-*/manifest.json"))
    assert len(manifests) == 1
    assert '"status": "failed"' in manifests[0].read_text(encoding="utf-8")
