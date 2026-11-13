"""Shared migration workflow; only the memory adapter changes between arms."""

import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from deterministic.agents.builder import build
from deterministic.agents.editor_contract import validate_editor
from deterministic.agents.model import ModelResult
from deterministic.agents.planner import MigrationTask, plan
from deterministic.agents.understanding import ContextPack, understand
from deterministic.agents.validator import ValidationResult, validate
from deterministic.ingestion.schemas import Evidence
from deterministic.memory.base import Context, MemoryAdapter, Record, Request
from deterministic.telemetry.logger import write_event

MAX_RETRIES = 2
CONTEXT_TOKEN_BUDGET = 4000


class WorkflowOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    pack: ContextPack
    tasks: list[MigrationTask]
    retrieved_ids: list[str]
    validation: ValidationResult
    generations: list[ModelResult]
    retries: int = Field(ge=0)


class ContextTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    purpose: str
    evidence_ids: list[str]
    token_count: int = Field(ge=0)
    schema_version: int = 1


def run_workflow(
    evidence: Evidence,
    target: str,
    store: MemoryAdapter,
    output: Path,
    run_id: str,
    source_root: Path | None = None,
) -> WorkflowOutcome:
    """Persist common evidence, retrieve bounded context, build and validate."""
    run_dir = output.parent

    def persist(record: Record) -> None:
        started = time.perf_counter()
        store.persist_artifact(record)
        write_event(
            run_dir,
            run_id,
            "memory",
            "persist",
            started,
            kind=record.metadata.get("kind", "unknown"),
        )

    def retrieve(query: str, stage: str) -> Context:
        started = time.perf_counter()
        context = store.retrieve_context(
            Request(query=query, token_budget=CONTEXT_TOKEN_BUDGET, limit=50)
        )
        trace = ContextTrace(
            purpose=stage,
            evidence_ids=context.evidence_ids,
            token_count=context.token_count,
        )
        with (run_dir / "contexts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(trace.model_dump_json() + "\n")
        write_event(
            run_dir,
            run_id,
            "memory",
            "retrieve",
            started,
            purpose=stage,
            record_count=len(context.records),
            context_tokens=context.token_count,
        )
        return context

    for entity in evidence.entities:
        if evidence.scope_id == "project-editor" and entity.kind not in {"module", "manifest"}:
            continue
        persist(
            Record(
                record_id=entity.entity_id,
                content=(
                    f"SUMMARY: {evidence.summaries[entity.entity_id]}\nSOURCE:\n{entity.content}"
                    if entity.kind in {"module", "manifest"}
                    else entity.content
                ),
                provenance=[entity.path],
                metadata={
                    "kind": entity.kind,
                    "revision": entity.revision,
                    "role": entity.role,
                },
                vector=evidence.embeddings[entity.entity_id],
            )
        )
    for relation in evidence.relations:
        persist(
            Record(
                record_id=relation.relation_id,
                content=f"{relation.kind} {relation.source_id} {relation.target_id}",
                provenance=[relation.provenance],
                metadata={
                    "kind": "relation",
                    "relation": relation.kind,
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                },
            )
        )
    query = (
        "backend/project_editor/main.py contracts.py merge.py upstream.py "
        "api projects GET PUT conflict uncertain frontend"
        if evidence.scope_id == "project-editor"
        else "repository modules contracts entrypoints"
    )
    global_context = retrieve(query, "understand_plan")
    pack = understand(evidence, global_context)
    tasks = plan(evidence, target, available_ids=set(pack.evidence_ids))
    retrieved_ids = list(global_context.evidence_ids)
    generations: list[ModelResult] = []
    for task in tasks:
        persist(
            Record(
                record_id=f"task:{task.order}:{task.source_path}",
                content=task.model_dump_json(),
                provenance=task.evidence_ids,
                metadata={"kind": "task", "order": str(task.order)},
            )
        )
        task_query = f"{task.source_path} contracts merge upstream api projects 409 504 422"
        context = retrieve(task_query, f"build:{task.order}")
        if not any(task.source_path in record.provenance for record in context.records):
            raise RuntimeError(f"Memory did not retrieve task evidence for {task.source_path}")
        retrieved_ids.extend(context.evidence_ids)
        artifact = build(task, evidence, output, target, context.records, generations=generations)
        if generations:
            generation = generations[-1]
            write_event(
                run_dir,
                run_id,
                "model",
                "generation",
                input_tokens=generation.prompt_tokens,
                output_tokens=generation.completion_tokens,
                model=generation.model,
                duration_ms=generation.duration_ms,
                cost=generation.cost_usd,
                attempt=0,
            )
        persist(
            Record(
                record_id=artifact.resolve().as_posix(),
                content=artifact.read_text(encoding="utf-8"),
                provenance=task.evidence_ids,
                metadata={"kind": "artifact", "path": task.target_path},
            )
        )

    def check() -> ValidationResult:
        started = time.perf_counter()
        result = (
            validate_editor(output, source_root)
            if evidence.scope_id == "project-editor"
            else validate(output, target, [case.model_dump() for case in evidence.behavioral_cases])
        )
        write_event(
            run_dir,
            run_id,
            "validate",
            "validation_finished",
            started,
            passed=result.passed,
            compile_passed=result.checks["syntax_or_compile"],
            behavior_passed=result.checks["behavioral"],
        )
        return result

    result = check()
    retries = 0
    while not result.passed and retries < MAX_RETRIES and evidence.scope_id == "project-editor":
        persist(
            Record(
                record_id=f"validation:{retries}",
                content=result.model_dump_json(),
                provenance=[task.target_path for task in tasks],
                metadata={"kind": "validation", "passed": "false"},
            )
        )
        retries += 1
        task = tasks[-1]
        context = retrieve(task_query + " validation feedback", f"retry:{retries}")
        retrieved_ids.extend(context.evidence_ids)
        artifact = build(
            task,
            evidence,
            output,
            target,
            context.records,
            generations=generations,
            feedback=result.output,
        )
        generation = generations[-1]
        write_event(
            run_dir,
            run_id,
            "model",
            "generation",
            input_tokens=generation.prompt_tokens,
            output_tokens=generation.completion_tokens,
            model=generation.model,
            duration_ms=generation.duration_ms,
            cost=generation.cost_usd,
            attempt=retries,
        )
        persist(
            Record(
                record_id=artifact.resolve().as_posix(),
                content=artifact.read_text(encoding="utf-8"),
                provenance=task.evidence_ids,
                metadata={"kind": "artifact", "path": task.target_path},
            )
        )
        result = check()
    persist(
        Record(
            record_id="validation:final",
            content=result.model_dump_json(),
            provenance=[task.target_path for task in tasks],
            metadata={"kind": "validation", "passed": str(result.passed).lower()},
        )
    )
    return WorkflowOutcome(
        pack=pack,
        tasks=tasks,
        retrieved_ids=retrieved_ids,
        validation=result,
        generations=generations,
        retries=retries,
    )
