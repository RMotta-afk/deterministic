"""Report every paired attempt, including failed migrations."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deterministic.agents.graph import ContextTrace
from deterministic.agents.model import ModelResult
from deterministic.agents.validator import ValidationResult
from deterministic.memory.base import Record
from deterministic.telemetry.logger import Event, RunManifest

# Reviewed against the pinned Editor source and its preserved API boundary.
EDITOR_RELEVANT_PATHS = frozenset(
    {
        "backend/project_editor/main.py",
        "backend/project_editor/contracts.py",
        "backend/project_editor/merge.py",
        "backend/project_editor/upstream.py",
        "frontend/src/api.ts",
        "frontend/src/contracts.ts",
        "upstream/records_api/main.py",
        "docs/sdd/api-contract.md",
    }
)


class RunReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    run_id: str
    pair_id: str | None
    project_id: str
    revision: str
    direction: str
    memory: str
    status: Literal["complete", "failed", "incomplete"]
    validation_passed: bool | None
    contract_checks_passed: int
    contract_checks_total: int
    input_tokens: int
    output_tokens: int
    runtime_provider_cost_usd: float | None
    retrieval_ms: float
    persist_ms: float
    generation_ms: float
    validation_ms: float
    end_to_end_ms: float
    retries: int
    context_word_estimates_by_step: list[int]
    evidence_recall: float | None
    evidence_precision: float | None
    error: str | None
    settings_signature: str | None = None
    runtime_embedding_tokens: int = 0
    runtime_embedding_ms: float = 0
    shared_preprocessing_tokens: int = 0
    shared_preprocessing_ms: float = 0
    shared_preprocessing_cost_usd: float | None = None
    actual_models: list[str] = Field(default_factory=list)
    arm_order: str | None = None


class PairReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    pair_id: str
    project_id: str
    revision: str
    direction: str
    vector_status: str
    graph_status: str
    vector_passed: bool
    graph_passed: bool
    delta_graph_minus_vector_input_tokens: int
    delta_graph_minus_vector_retrieval_ms: float
    delta_graph_minus_vector_end_to_end_ms: float
    delta_graph_minus_vector_runtime_provider_cost_usd: float | None


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: int = 1
    runs: list[RunReport]
    pairs: list[PairReport]
    excluded_pairs: list[dict[str, str]]
    success_rate_by_memory: dict[str, float]
    runtime_provider_cost_per_success_by_memory: dict[str, float | None]
    configuration_groups: list[dict[str, str | int | float]]


def _relevance(path: Path, traces: list[ContextTrace]) -> tuple[float | None, float | None]:
    memory_file = next(
        (
            candidate
            for candidate in (path / "vector.jsonl", path / "graph.jsonl")
            if candidate.exists()
        ),
        None,
    )
    if not memory_file:
        return None, None
    records = {
        record.record_id: record
        for line in memory_file.read_text(encoding="utf-8").splitlines()
        if line
        for record in [Record.model_validate_json(line)]
    }
    recalls = []
    precisions = []
    for trace in traces:
        if trace.purpose not in {"understand_plan", "build:0"}:
            continue
        source_records = [
            records[record_id]
            for record_id in trace.evidence_ids
            if record_id in records and records[record_id].metadata.get("kind") == "module"
        ]
        paths = {path for record in source_records for path in record.provenance}
        recalls.append(len(paths & EDITOR_RELEVANT_PATHS) / len(EDITOR_RELEVANT_PATHS))
        precisions.append(
            sum(bool(set(record.provenance) & EDITOR_RELEVANT_PATHS) for record in source_records)
            / len(source_records)
            if source_records
            else 0.0
        )
    if not recalls:
        return None, None
    return sum(recalls) / len(recalls), sum(precisions) / len(precisions)


def _run_report(row: dict) -> RunReport:
    path = Path(row["run_path"])
    manifest = None
    validation = None
    events = []
    traces = []
    model_responses = []
    try:
        manifest = RunManifest.model_validate_json(
            (path / "manifest.json").read_text(encoding="utf-8")
        )
        validation = ValidationResult.model_validate_json(
            (path / "validation.json").read_text(encoding="utf-8")
        )
        events = [
            Event.model_validate_json(line)
            for line in (path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        if (path / "contexts.jsonl").exists():
            traces = [
                ContextTrace.model_validate_json(line)
                for line in (path / "contexts.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
        if (path / "model_responses.jsonl").exists():
            model_responses = [
                ModelResult.model_validate_json(line)
                for line in (path / "model_responses.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ]
    except (OSError, ValueError):
        pass
    if manifest is None or validation is None:
        status = "incomplete"
    elif manifest.status == "failed":
        status = "failed"
    elif manifest.status == "complete" and validation.passed and (path / "output").exists():
        status = "complete"
    else:
        status = "incomplete"
    generation = [event for event in events if event.event == "generation"]
    embedding = [event for event in events if event.event == "embedding"]
    provider_events = generation + embedding
    known_cost = bool(provider_events) and all(event.cost is not None for event in provider_events)
    recall, precision = (
        _relevance(path, traces)
        if manifest is not None and manifest.settings.get("scope_id") == "project-editor"
        else (None, None)
    )
    contract_checks = (
        {
            key: value
            for key, value in validation.checks.items()
            if key not in {"syntax_or_compile", "behavioral"}
        }
        if validation
        else {}
    )
    terminal = next(
        (event for event in reversed(events) if event.event in {"run_finished", "run_failed"}),
        None,
    )
    return RunReport(
        run_id=row["run_id"],
        pair_id=row["pair_id"],
        project_id=row["project_id"],
        revision=row["revision"],
        direction=row["direction"],
        memory=row["memory"],
        status=status,
        validation_passed=validation.passed if validation else None,
        contract_checks_passed=sum(contract_checks.values()),
        contract_checks_total=len(contract_checks),
        input_tokens=sum(event.input_tokens for event in generation),
        output_tokens=sum(event.output_tokens for event in generation),
        runtime_provider_cost_usd=(
            sum(event.cost for event in provider_events) if known_cost else None
        ),
        retrieval_ms=sum(event.duration_ms for event in events if event.event == "retrieve"),
        persist_ms=sum(event.duration_ms for event in events if event.event == "persist"),
        generation_ms=sum(event.duration_ms for event in generation),
        validation_ms=sum(
            event.duration_ms for event in events if event.event == "validation_finished"
        ),
        end_to_end_ms=terminal.duration_ms if terminal else 0,
        retries=sum(int(event.details.get("attempt", 0)) > 0 for event in generation),
        context_word_estimates_by_step=[trace.token_count for trace in traces],
        evidence_recall=recall,
        evidence_precision=precision,
        error=validation.output[:1000] if validation and not validation.passed else None,
        settings_signature=(
            hashlib.sha256(
                json.dumps(
                    {key: value for key, value in manifest.settings.items() if key != "arm_order"},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            if manifest
            else None
        ),
        runtime_embedding_tokens=sum(event.input_tokens for event in embedding),
        runtime_embedding_ms=sum(event.duration_ms for event in embedding),
        shared_preprocessing_tokens=(
            int(manifest.settings.get("preprocessing_summary_input_tokens", 0))
            + int(manifest.settings.get("preprocessing_summary_output_tokens", 0))
            + int(manifest.settings.get("preprocessing_embedding_tokens", 0))
            if manifest
            else 0
        ),
        shared_preprocessing_ms=float(manifest.settings.get("preprocessing_ms", 0))
        if manifest
        else 0,
        shared_preprocessing_cost_usd=(
            float(manifest.settings["preprocessing_cost_usd"])
            if manifest and "preprocessing_cost_usd" in manifest.settings
            else None
        ),
        actual_models=sorted({response.model for response in model_responses}),
        arm_order=str(manifest.settings.get("arm_order")) if manifest else None,
    )


def evaluate(runs: list[dict], output: Path) -> dict:
    reports = [_run_report(row) for row in runs]
    grouped: dict[str, list[RunReport]] = {}
    for report in reports:
        if report.pair_id:
            grouped.setdefault(report.pair_id, []).append(report)
    paired = []
    excluded = []
    for pair_id, arms in grouped.items():
        vector = next((arm for arm in arms if arm.memory == "vector"), None)
        graph = next((arm for arm in arms if arm.memory == "graph"), None)
        if (
            not vector
            or not graph
            or vector.status == "incomplete"
            or graph.status == "incomplete"
            or vector.project_id != graph.project_id
            or vector.revision != graph.revision
            or vector.direction != graph.direction
            or vector.settings_signature != graph.settings_signature
            or (
                vector.actual_models
                and graph.actual_models
                and vector.actual_models != graph.actual_models
            )
        ):
            excluded.append(
                {"pair_id": pair_id, "reason": "missing, incomplete, or incomparable arm"}
            )
            continue
        paired.append(
            PairReport(
                pair_id=pair_id,
                project_id=vector.project_id,
                revision=vector.revision,
                direction=vector.direction,
                vector_status=vector.status,
                graph_status=graph.status,
                vector_passed=bool(vector.validation_passed),
                graph_passed=bool(graph.validation_passed),
                delta_graph_minus_vector_input_tokens=graph.input_tokens - vector.input_tokens,
                delta_graph_minus_vector_retrieval_ms=graph.retrieval_ms - vector.retrieval_ms,
                delta_graph_minus_vector_end_to_end_ms=graph.end_to_end_ms - vector.end_to_end_ms,
                delta_graph_minus_vector_runtime_provider_cost_usd=(
                    graph.runtime_provider_cost_usd - vector.runtime_provider_cost_usd
                    if graph.runtime_provider_cost_usd is not None
                    and vector.runtime_provider_cost_usd is not None
                    else None
                ),
            )
        )
    rates = {}
    cost_per_success = {}
    for arm in ("vector", "graph"):
        completed = [
            report for report in reports if report.memory == arm and report.status != "incomplete"
        ]
        successes = sum(bool(report.validation_passed) for report in completed)
        rates[arm] = successes / len(completed) if completed else 0.0
        cost_per_success[arm] = (
            sum(report.runtime_provider_cost_usd for report in completed) / successes
            if successes
            and all(report.runtime_provider_cost_usd is not None for report in completed)
            else None
        )
    report = EvaluationReport(
        runs=reports,
        pairs=paired,
        excluded_pairs=excluded,
        success_rate_by_memory=rates,
        runtime_provider_cost_per_success_by_memory=cost_per_success,
        configuration_groups=[
            {
                "settings_signature": signature,
                "run_count": len(group),
                "vector_success_rate": (
                    sum(bool(run.validation_passed) for run in group if run.memory == "vector")
                    / sum(run.memory == "vector" for run in group)
                    if any(run.memory == "vector" for run in group)
                    else 0.0
                ),
                "graph_success_rate": (
                    sum(bool(run.validation_passed) for run in group if run.memory == "graph")
                    / sum(run.memory == "graph" for run in group)
                    if any(run.memory == "graph" for run in group)
                    else 0.0
                ),
            }
            for signature, group in sorted(
                (
                    (
                        signature,
                        [
                            run
                            for run in reports
                            if run.settings_signature == signature and run.status != "incomplete"
                        ],
                    )
                    for signature in {
                        run.settings_signature
                        for run in reports
                        if run.settings_signature and run.status != "incomplete"
                    }
                ),
                key=lambda item: item[0],
            )
        ],
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report.model_dump()
