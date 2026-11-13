"""Validated interface shared by the isolated memory implementations."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    query: str
    token_budget: int = Field(gt=0)
    limit: int = Field(default=10, gt=0)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    record_id: str
    content: str
    provenance: list[str]
    metadata: dict[str, str] = {}
    vector: list[float] = []


class Context(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    records: list[Record]
    token_count: int = Field(ge=0)
    evidence_ids: list[str]


class PersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    record_id: str
    persisted: bool


class MemoryAdapter(ABC):
    @abstractmethod
    def retrieve_context(self, request: Request) -> Context: ...

    @abstractmethod
    def persist_artifact(self, record: Record) -> PersistResult: ...
