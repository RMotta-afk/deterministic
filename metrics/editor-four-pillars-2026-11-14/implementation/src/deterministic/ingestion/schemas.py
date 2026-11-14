"""Strict, versioned records shared by ingestion and memory."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Entity(Boundary):
    entity_id: str = Field(min_length=1)
    kind: Literal["module", "class", "function", "type", "variable", "test", "manifest"]
    name: str
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str
    language: Literal["python", "typescript", "other"]
    revision: str
    role: Literal["migrate", "contract"] = "migrate"
    schema_version: Literal[1] = 1


class Relation(Boundary):
    relation_id: str
    source_id: str
    target_id: str
    kind: str
    provenance: str
    schema_version: Literal[1] = 1


class BehaviorCase(Boundary):
    function: str
    arguments: list[int | float | str | bool]
    expected: int | float | str | bool


class PreprocessingStats(Boundary):
    summary_model: str = "source-excerpt-v1"
    embedding_model: str = "deterministic-hash-1"
    summary_input_tokens: int = Field(default=0, ge=0)
    summary_output_tokens: int = Field(default=0, ge=0)
    embedding_input_tokens: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    schema_version: Literal[1] = 1


class Evidence(Boundary):
    entities: list[Entity]
    relations: list[Relation]
    summaries: dict[str, str]
    embeddings: dict[str, list[float]]
    revision: str
    language: Literal["python", "typescript"]
    behavioral_cases: list["BehaviorCase"] = []
    scope_id: str | None = None
    source_commit: str | None = None
    preprocessing: PreprocessingStats = Field(default_factory=PreprocessingStats)
    schema_version: Literal[1] = 1
