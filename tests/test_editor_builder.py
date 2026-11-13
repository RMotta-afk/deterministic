from pathlib import Path

from deterministic.agents.builder import build
from deterministic.agents.model import ModelResult
from deterministic.agents.planner import plan
from deterministic.ingestion.schemas import Entity, Evidence
from deterministic.memory.base import Record


class FakeModel:
    def __init__(self, text: str):
        self.text = text
        self.prompt = ""

    def complete(self, _system: str, user: str) -> ModelResult:
        self.prompt = user
        return ModelResult(
            text=self.text,
            model="fake-model",
            prompt_tokens=10,
            completion_tokens=20,
            duration_ms=1,
        )


def test_editor_builder_uses_retrieved_context_only(tmp_path: Path):
    entities = [
        Entity(
            entity_id=f"e{i}",
            kind="module",
            name=name,
            path=f"backend/project_editor/{name}",
            start_line=1,
            end_line=1,
            content=f"hidden source {name}",
            language="python",
            revision="r",
        )
        for i, name in enumerate(("__init__.py", "contracts.py", "main.py"))
    ]
    evidence = Evidence(
        entities=entities,
        relations=[],
        summaries={},
        embeddings={},
        revision="r",
        language="python",
        scope_id="project-editor",
    )
    tasks = plan(evidence, "typescript")
    assert len(tasks) == 1 and tasks[0].target_path == "server.ts"
    model = FakeModel("const observed = true;")
    generated = []
    artifact = build(
        tasks[0],
        evidence,
        tmp_path,
        "typescript",
        context=[Record(record_id="r1", content="retrieved contract", provenance=["contracts.py"])],
        model=model,
        generations=generated,
    )
    assert artifact.read_text(encoding="utf-8").startswith("// @ts-nocheck")
    assert "retrieved contract" in model.prompt
    assert "hidden source" not in model.prompt
    assert generated[0].prompt_tokens == 10
