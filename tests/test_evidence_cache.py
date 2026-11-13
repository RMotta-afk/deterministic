import pytest
from pydantic import ValidationError

from deterministic.ingestion.cache import ingest_evidence
from deterministic.ingestion.schemas import Evidence


def test_evidence_ids_are_stable_and_cache_is_reused(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "main.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    first, first_hit = ingest_evidence(root, "pinned-revision", tmp_path / "cache")
    second, second_hit = ingest_evidence(root, "pinned-revision", tmp_path / "cache")
    assert not first_hit and second_hit
    assert [item.entity_id for item in first.entities] == [
        item.entity_id for item in second.entities
    ]


def test_evidence_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {
                "entities": [],
                "relations": [],
                "summaries": {},
                "embeddings": {},
                "revision": "r1",
                "language": "python",
                "unexpected": True,
            }
        )
