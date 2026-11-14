"""Build a cited repository context pack."""

from pydantic import BaseModel, ConfigDict

from deterministic.ingestion.schemas import Evidence
from deterministic.memory.base import Context


class ContextPack(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    summary: str
    evidence_ids: list[str]
    schema_version: int = 1


def understand(evidence: Evidence, context: Context | None = None) -> ContextPack:
    if context is not None:
        paths = sorted({path for record in context.records for path in record.provenance})
        return ContextPack(
            summary=f"Retrieved {len(context.records)} records for {evidence.language} revision "
            f"{evidence.revision}; paths: {', '.join(paths)}",
            evidence_ids=context.evidence_ids,
        )
    return ContextPack(
        summary=(
            f"{len(evidence.entities)} entities in {evidence.language} revision {evidence.revision}"
        ),
        evidence_ids=[e.entity_id for e in evidence.entities],
    )
