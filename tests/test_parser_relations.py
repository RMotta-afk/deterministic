"""Package imports must create provenance-backed graph edges."""

from pathlib import Path

from deterministic.ingestion.parser import parse_source
from deterministic.ingestion.scope import load_scope


def test_editor_package_imports_resolve_to_scoped_modules():
    root = Path(__file__).parents[1]
    scope = load_scope(root / "fixtures/benchmark-scope.json", "project-editor")
    entities, relations = parse_source(root / "fixtures/project-editor", "test-revision", scope)
    paths = {entity.entity_id: entity.path for entity in entities}
    edges = {(paths[edge.source_id], paths[edge.target_id]) for edge in relations}
    package = "backend/project_editor/"
    assert {
        (package + "main.py", package + "contracts.py"),
        (package + "main.py", package + "merge.py"),
        (package + "main.py", package + "upstream.py"),
        (package + "merge.py", package + "contracts.py"),
        (package + "upstream.py", package + "contracts.py"),
    } <= edges
    assert all(edge.kind == "IMPORTS" and edge.provenance for edge in relations)


def test_relative_imports_resolve_without_guessing_external_packages(tmp_path: Path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "main.py").write_text("from .helper import run\nimport httpx\n", encoding="utf-8")
    (package / "helper.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    entities, relations = parse_source(tmp_path, "test-revision")
    paths = {entity.entity_id: entity.path for entity in entities}
    assert [(paths[edge.source_id], paths[edge.target_id]) for edge in relations] == [
        ("package/main.py", "package/helper.py")
    ]
