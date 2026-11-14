"""Graph retrieval must use explicit links, including lexically disjoint hops."""

from pathlib import Path

from deterministic.memory.base import Record, Request
from deterministic.memory.graph_memory import GraphMemory
from deterministic.memory.vector_memory import VectorMemory


def _records() -> list[Record]:
    nodes = [
        Record(
            record_id="a", content="entry anchor", provenance=["a.py"], metadata={"kind": "module"}
        ),
        Record(
            record_id="b", content="opaque relay", provenance=["b.py"], metadata={"kind": "module"}
        ),
        Record(
            record_id="c",
            content="destination fact",
            provenance=["c.py"],
            metadata={"kind": "module"},
        ),
    ]
    edges = [
        Record(
            record_id="a-b",
            content="a.py IMPORTS b.py",
            provenance=["a.py:line:1"],
            metadata={
                "kind": "relation",
                "relation": "IMPORTS",
                "source_id": "a",
                "target_id": "b",
            },
        ),
        Record(
            record_id="b-c",
            content="b.py IMPORTS c.py",
            provenance=["b.py:line:1"],
            metadata={
                "kind": "relation",
                "relation": "IMPORTS",
                "source_id": "b",
                "target_id": "c",
            },
        ),
    ]
    return nodes + edges


def test_graph_follows_two_hops_even_without_lexical_overlap(tmp_path: Path):
    memory = GraphMemory(tmp_path / "graph.jsonl", "local")
    for record in _records():
        memory.persist_artifact(record)
    context = memory.retrieve_context(Request(query="entry", anchor_ids=["a"], token_budget=30))
    assert context.evidence_ids == ["a", "a-b", "b", "b-c", "c"]
    assert context.token_count <= 30


def test_vector_receives_the_same_anchor_and_relation_records(tmp_path: Path):
    memory = VectorMemory(tmp_path / "vector.jsonl", "local")
    for record in _records():
        memory.persist_artifact(record)
    context = memory.retrieve_context(Request(query="entry", anchor_ids=["a"], token_budget=30))
    assert context.evidence_ids[0] == "a"
    assert {"a-b", "b-c"} <= set(memory.records)
