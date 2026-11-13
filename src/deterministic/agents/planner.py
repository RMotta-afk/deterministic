"""Create ordered migration tasks from the shared evidence."""

from pydantic import BaseModel, ConfigDict, Field

from deterministic.ingestion.schemas import Evidence


class MigrationTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    order: int = Field(ge=0)
    source_path: str
    target_path: str
    evidence_ids: list[str]


def plan(
    evidence: Evidence, target: str, available_ids: set[str] | None = None
) -> list[MigrationTask]:
    if evidence.scope_id == "project-editor" and target == "typescript":
        backend = [
            entity
            for entity in evidence.entities
            if entity.role == "migrate"
            and entity.kind == "module"
            and entity.path.endswith(".py")
            and (available_ids is None or entity.entity_id in available_ids)
        ]
        if not any(entity.path.endswith("/main.py") for entity in backend):
            raise ValueError("Editor backend entrypoint is missing")
        return [
            MigrationTask(
                order=0,
                source_path="backend/project_editor/main.py",
                target_path="server.ts",
                evidence_ids=[entity.entity_id for entity in backend],
            )
        ]
    paths = sorted(
        {e.path for e in evidence.entities if e.language != "other" and e.role == "migrate"}
    )
    suffix = ".py" if target == "python" else ".ts"
    return [
        MigrationTask(
            order=i,
            source_path=p,
            target_path=(p[:-3] if p.endswith(".py") else p[:-3] if p.endswith(".ts") else p)
            + suffix,
            evidence_ids=[e.entity_id for e in evidence.entities if e.path == p],
        )
        for i, p in enumerate(paths)
    ]
