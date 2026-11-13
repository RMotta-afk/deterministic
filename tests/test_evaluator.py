"""A failed migration is a scored outcome, not an absent pair."""

from pathlib import Path

from deterministic.agents.validator import ValidationResult
from deterministic.telemetry.evaluator import evaluate
from deterministic.telemetry.logger import RunManifest, write_event


def test_failed_arm_remains_in_pair(tmp_path: Path):
    rows = []
    for arm, status in (("vector", "complete"), ("graph", "failed")):
        path = tmp_path / arm
        path.mkdir()
        if status == "complete":
            (path / "output").mkdir()
            (path / "output" / "server.ts").write_text("const ok = true;", encoding="utf-8")
        (path / "manifest.json").write_text(
            RunManifest(
                run_id=arm,
                pair_id="pair",
                project_id="editor",
                revision="revision",
                direction="python-to-typescript",
                memory=arm,
                status=status,
                settings={},
            ).model_dump_json(),
            encoding="utf-8",
        )
        (path / "validation.json").write_text(
            ValidationResult(
                passed=status == "complete",
                checks={
                    "syntax_or_compile": status == "complete",
                    "behavioral": status == "complete",
                },
                output="builder error" if status == "failed" else "",
            ).model_dump_json(),
            encoding="utf-8",
        )
        write_event(path, arm, "migrate", "run_finished" if status == "complete" else "run_failed")
        rows.append(
            {
                "run_id": arm,
                "pair_id": "pair",
                "project_id": "editor",
                "revision": "revision",
                "direction": "python-to-typescript",
                "memory": arm,
                "status": status,
                "run_path": str(path),
            }
        )
    report = evaluate(rows, tmp_path / "evaluation")
    assert len(report["pairs"]) == 1
    assert report["pairs"][0]["graph_passed"] is False
    assert report["success_rate_by_memory"] == {"vector": 1.0, "graph": 0.0}
    assert report["runs"][1]["error"] == "builder error"
