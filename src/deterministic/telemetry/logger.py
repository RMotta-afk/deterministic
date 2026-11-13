"""Versioned run manifests and JSONL telemetry."""

import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from deterministic.ingestion.schemas import PreprocessingStats


class IngestManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    operation_id: str
    profile: str | None
    status: Literal["running", "ready", "failed"]
    project_id: str | None = None
    revision: str | None = None
    cache_hit: bool | None = None
    entity_count: int | None = None
    preprocessing: PreprocessingStats | None = None
    error: str | None = None


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int = 1
    run_id: str
    pair_id: str | None
    project_id: str
    revision: str
    direction: str
    memory: str
    status: str
    settings: dict[str, str | int | float | bool]


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int = 1
    timestamp: float
    stage: str
    run_id: str
    event: str
    duration_ms: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None
    details: dict[str, str | int | float | bool] = {}


def write_event(
    path: Path, run_id: str, stage: str, event: str, started: float | None = None, **details
):
    raw_cost = details.pop("cost", None)
    e = Event(
        timestamp=time.time(),
        stage=stage,
        run_id=run_id,
        event=event,
        duration_ms=(
            float(details.pop("duration_ms"))
            if "duration_ms" in details
            else (time.perf_counter() - started) * 1000
            if started
            else 0
        ),
        input_tokens=int(details.pop("input_tokens", 0)),
        output_tokens=int(details.pop("output_tokens", 0)),
        cost=float(raw_cost) if raw_cost is not None else None,
        details=details,
    )
    with (path / "metrics.jsonl").open("a", encoding="utf-8") as f:
        f.write(e.model_dump_json() + "\n")
