from pathlib import Path

import tiktoken

from deterministic.agents.model import ModelResult, ModelSettings
from deterministic.memory.base import Record
from deterministic.memory.graph_memory import GraphMemory
from deterministic.study import editor_benchmark as benchmark


def test_exact_budget_and_relevance_include_serialization():
    records = [
        Record(record_id="a", content="ação relação", provenance=[]),
        Record(record_id="b", content="unrelated " * 80, provenance=[]),
    ]
    text, ids, count, useful = benchmark.pack(records, ["a"], 20)
    assert count == len(tiktoken.get_encoding(benchmark.ENCODING).encode(text))
    assert count <= 20
    assert ids == ["a"]
    assert useful == count


def test_truth_and_retrieved_support_are_separate():
    question = benchmark.Question(
        id="q", kind="local", query="status", anchor="a", expected="409", relevant=["a"]
    )
    result = benchmark.judge(benchmark.Answer(answer="409", citations=[]), question, [])
    assert result["correct"] and result["hallucination"] is False
    assert result["evidence_complete"] is False and result["citations_valid"] is False
    assert (
        benchmark.judge(benchmark.Answer(answer="200", citations=["a"]), question, ["a"])[
            "hallucination"
        ]
        is True
    )
    abstention = benchmark.judge(benchmark.Answer(answer="UNKNOWN", citations=[]), question, [])
    assert abstention["hallucination"] is None and not abstention["correct"]
    alias = benchmark.judge(benchmark.Answer(answer="HTTP 409.", citations=["a"]), question, ["a"])
    assert alias["correct"] and alias["hallucination"] is False
    prose = benchmark.judge(
        benchmark.Answer(answer="I cannot determine this", citations=[]), question, []
    )
    assert prose["hallucination"] is None and not prose["correct"]


def test_superseded_requirement_is_not_current_truth():
    protocol = benchmark.source_protocol(Path("fixtures/project-editor"))
    question = protocol.questions[-1]
    old = benchmark.judge(
        benchmark.Answer(answer="6", citations=["requirement:v1"]), question, ["requirement:v1"]
    )
    assert old["hallucination"] is True and not old["correct"]


def test_failure_preserves_planned_denominator_and_paid_prefix(tmp_path, monkeypatch):
    protocol = benchmark.source_protocol(Path("fixtures/project-editor"))
    monkeypatch.setenv("FALKORDB_HOST", "unused")
    monkeypatch.setattr(benchmark, "GraphMemory", lambda path, name, host: GraphMemory(path, name))

    class Client:
        count = 0

        def __init__(self, settings):
            pass

        def complete(self, system, prompt, **kwargs):
            self.count += 1
            if self.count == 2:
                raise RuntimeError("injected failure after paid analyst")
            question = next(q for q in protocol.questions if q.query in prompt)
            answer = benchmark.Answer(answer=question.expected, citations=[])
            return ModelResult(
                text=answer.model_dump_json(),
                model="mock",
                prompt_tokens=10,
                completion_tokens=2,
                duration_ms=1,
                cost_usd=0.001,
            )

    monkeypatch.setattr(benchmark, "ChatModel", Client)
    arm = benchmark.run_arm(
        protocol,
        protocol.records,
        0,
        "graph",
        tmp_path,
        ModelSettings(model="mock", api_key="mock"),
    )
    report = benchmark.summarize(arm)
    assert report["planned"] == 12 and report["completed"] == 11
    assert report["accuracy"] == 11 / 12
    assert report["observed_chat_tokens"] == 23 * 12
    assert report["chat_tokens"] is None
    assert arm.calls[0].response.cost_usd == 0.001


def test_indexing_failure_still_saves_entire_arm(tmp_path, monkeypatch):
    protocol = benchmark.source_protocol(Path("fixtures/project-editor"))
    monkeypatch.setenv("FALKORDB_HOST", "unused")

    class BrokenStore:
        def persist_artifact(self, record):
            raise RuntimeError("injected indexing failure")

    monkeypatch.setattr(benchmark, "GraphMemory", lambda *args: BrokenStore())
    arm = benchmark.run_arm(
        protocol,
        protocol.records,
        0,
        "graph",
        tmp_path,
        ModelSettings(model="mock", api_key="mock"),
    )
    assert benchmark.summarize(arm)["accuracy"] == 0
    assert len(arm.observations) == 12 and arm.status == "failed"
    assert (tmp_path / arm.id / "run.json").exists()
