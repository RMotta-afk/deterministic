import shutil
from pathlib import Path

import pytest

from deterministic.agents.builder import build
from deterministic.agents.planner import MigrationTask
from deterministic.agents.validator import validate
from deterministic.ingestion.cache import ingest_evidence


@pytest.mark.parametrize(
    ("fixture", "target", "source_path"),
    [
        ("python", "typescript", "add.py"),
        ("typescript", "python", "add.ts"),
    ],
)
def test_controlled_direction_compiles_and_passes_behavior(
    fixture: str, target: str, source_path: str, tmp_path: Path
):
    if target == "typescript" and not shutil.which("tsc"):
        pytest.skip("TypeScript compiler is provided by the Docker runtime")
    root = Path(__file__).parents[1] / "fixtures" / fixture
    evidence, _ = ingest_evidence(root, f"fixture-{fixture}", tmp_path / "cache")
    task = MigrationTask(
        order=0,
        source_path=source_path,
        target_path="add.ts" if target == "typescript" else "add.py",
        evidence_ids=[e.entity_id for e in evidence.entities if e.path == source_path],
    )
    output = tmp_path / "output"
    build(task, evidence, output, target)
    result = validate(output, target, [case.model_dump() for case in evidence.behavioral_cases])
    assert result.passed, result.output
