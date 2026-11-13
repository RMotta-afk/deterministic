"""Command-line entry point for ingestion, migration, and evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from deterministic.agents.builder import EDITOR_PROMPT_VERSION
from deterministic.agents.graph import CONTEXT_TOKEN_BUDGET, MAX_RETRIES, run_workflow
from deterministic.agents.model import ModelSettings
from deterministic.agents.validator import ValidationResult
from deterministic.catalog import Catalog, Project
from deterministic.ingestion.cache import (
    EMBEDDING_VERSION,
    PARSER_VERSION,
    evidence_cache_key,
    ingest_evidence,
)
from deterministic.ingestion.repo_loader import load_source
from deterministic.ingestion.schemas import Evidence
from deterministic.ingestion.scope import load_scope
from deterministic.memory.graph_memory import GraphMemory
from deterministic.memory.vector_memory import VectorMemory
from deterministic.telemetry.evaluator import evaluate
from deterministic.telemetry.logger import IngestManifest, RunManifest, write_event


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deterministic", description="Paired migration benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("source")
    ingest.add_argument("--revision", help="Exact Git commit to load")
    ingest.add_argument("--scope-file", type=Path, help="Validated benchmark scope manifest")
    ingest.add_argument("--profile", help="Repository ID within the scope manifest")
    migrate = commands.add_parser("migrate")
    migrate.add_argument("--project")
    migrate.add_argument("--target", choices=("python", "typescript"))
    migrate.add_argument("--memory", choices=("vector", "graph", "both"), default="both")
    migrate.add_argument("--repeat", type=int, default=1, help="Number of fresh paired attempts")
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--project", help="Limit the report to one indexed project")
    return parser


def _data_dir():
    return Path(os.environ.get("DETERMINISTIC_DATA_DIR", "data"))


def _ingest(
    source: str,
    pinned_revision: str | None = None,
    scope_file: Path | None = None,
    profile: str | None = None,
) -> int:
    data = _data_dir()
    if bool(scope_file) != bool(profile):
        raise ValueError("--scope-file and --profile must be supplied together")
    scope = load_scope(scope_file, profile) if scope_file and profile else None
    if scope and Path(source).name != scope.id:
        raise ValueError(f"source name must match benchmark profile {scope.id}")
    if scope and pinned_revision and pinned_revision != scope.commit:
        raise ValueError("requested revision differs from pinned benchmark commit")
    operation_id = uuid.uuid4().hex
    run_dir = data / "runs" / f"ingest-{operation_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = IngestManifest(operation_id=operation_id, profile=profile, status="running")
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    started = time.perf_counter()
    write_event(
        run_dir, operation_id, "ingest", "ingest_started", started, profile=profile or "none"
    )
    snapshot = None
    project_id = None
    revision = None
    try:
        pinned = scope.commit if scope and source.startswith("https://") else pinned_revision
        snapshot = load_source(source, data / "cache" / "sources", pinned)
        if scope:
            content_hash = snapshot.revision.split("-")[-1]
            if content_hash != scope.content_sha256:
                raise ValueError(f"source content does not match pinned profile {scope.id}")
            missing = [
                root
                for root in (*scope.migration_roots, *scope.contract_roots, *scope.preserve_roots)
                if not (snapshot.path / root).exists()
            ]
            if missing:
                raise ValueError(f"benchmark profile {scope.id} has missing roots: {missing}")
        revision = f"{snapshot.revision}:scope:{scope.fingerprint}" if scope else snapshot.revision
        project_id = hashlib.sha256(f"{snapshot.source}\0{revision}".encode()).hexdigest()[:16]
        with Catalog(data / "catalog" / "projects.duckdb") as cat:
            cat.upsert_project(
                Project(
                    project_id=project_id,
                    source=snapshot.source,
                    revision=revision,
                    language="pending",
                    cache_path=str(snapshot.path),
                    status="ingesting",
                )
            )
        evidence, hit = ingest_evidence(snapshot.path, revision, data / "cache", scope)
        with Catalog(data / "catalog" / "projects.duckdb") as cat:
            cat.upsert_project(
                Project(
                    project_id=project_id,
                    source=snapshot.source,
                    revision=revision,
                    language=evidence.language,
                    cache_path=str(snapshot.path),
                    status="ready",
                )
            )
        manifest.project_id = project_id
        manifest.revision = revision
        manifest.cache_hit = hit
        manifest.entity_count = len(evidence.entities)
        manifest.preprocessing = evidence.preprocessing
        manifest.status = "ready"
        write_event(
            run_dir,
            operation_id,
            "ingest",
            "ingest_ready",
            started,
            project_id=project_id,
            cache_hit=hit,
            entity_count=len(evidence.entities),
            input_tokens=(
                evidence.preprocessing.summary_input_tokens
                + evidence.preprocessing.embedding_input_tokens
            ),
            output_tokens=evidence.preprocessing.summary_output_tokens,
            cost=evidence.preprocessing.cost_usd,
        )
        print(
            f"Ready: {project_id} revision={revision} "
            f"entities={len(evidence.entities)} cache_hit={hit}"
        )
        return 0
    except Exception as exc:
        manifest.status = "failed"
        manifest.project_id = project_id
        manifest.revision = revision
        manifest.error = f"{type(exc).__name__}: {str(exc)[:1000]}"
        if snapshot is not None and project_id is not None and revision is not None:
            with Catalog(data / "catalog" / "projects.duckdb") as cat:
                cat.upsert_project(
                    Project(
                        project_id=project_id,
                        source=snapshot.source,
                        revision=revision,
                        language="pending",
                        cache_path=str(snapshot.path),
                        status="failed",
                    )
                )
        write_event(run_dir, operation_id, "ingest", "ingest_failed", started, error=manifest.error)
        raise
    finally:
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def _migrate(
    project_id: str | None,
    target: str | None,
    memory: str,
    repeat: int = 1,
    reverse_order: bool = False,
) -> int:
    if repeat < 1 or repeat > 20:
        raise ValueError("--repeat must be between 1 and 20")
    if repeat > 1:
        return max(
            _migrate(project_id, target, memory, reverse_order=bool(index % 2))
            for index in range(repeat)
        )
    data = _data_dir()
    with Catalog(data / "catalog" / "projects.duckdb") as cat:
        projects = cat.list_ready_projects()
        project = (
            next((item for item in projects if item.project_id == project_id), None)
            if project_id
            else (projects[0] if len(projects) == 1 else None)
        )
        if project is None and project_id is None and projects:
            import sys

            if sys.stdin.isatty():
                for index, item in enumerate(projects, 1):
                    print(f"{index}. {item.project_id} {item.source} {item.language}")
                selection = input("Select project number: ").strip()
                if selection.isdigit() and 1 <= int(selection) <= len(projects):
                    project = projects[int(selection) - 1]
        if not project:
            raise ValueError(
                "Select a ready --project; available: " + ", ".join(p.project_id for p in projects)
            )
        target = target or ("typescript" if project.language == "python" else "python")
        evidence_path = data / "cache" / "evidence" / f"{evidence_cache_key(project.revision)}.json"
        if not evidence_path.exists():
            raise ValueError("No evidence cache for these model settings; run ingest again")
        evidence = Evidence.model_validate_json(evidence_path.read_text(encoding="utf-8"))
        if evidence.scope_id == "project-editor":
            if target != "typescript":
                raise ValueError("Editor proof of concept targets TypeScript")
            ModelSettings.from_environment()
            if evidence.preprocessing.summary_model != (
                os.getenv("MIGRATION_SUMMARY_MODEL") or "source-excerpt-v1"
            ) or evidence.preprocessing.embedding_model != (
                os.getenv("MIGRATION_EMBEDDING_MODEL") or EMBEDDING_VERSION
            ):
                raise ValueError(
                    "Migration preprocessing settings differ from the ingested snapshot"
                )
            if (
                evidence.preprocessing.summary_model == "source-excerpt-v1"
                or evidence.preprocessing.embedding_model == EMBEDDING_VERSION
            ):
                raise ValueError(
                    "Scored Editor migration requires MIGRATION_SUMMARY_MODEL and "
                    "MIGRATION_EMBEDDING_MODEL at ingest and migrate"
                )
            if not os.getenv("QDRANT_URL") or not os.getenv("FALKORDB_HOST"):
                raise ValueError("Editor proof of concept requires QDRANT_URL and FALKORDB_HOST")
        arms = (
            ("graph", "vector")
            if reverse_order and memory == "both"
            else (("vector", "graph") if memory == "both" else (memory,))
        )
        pair_id = uuid.uuid4().hex if len(arms) == 2 else None
        failures = 0
        for arm in arms:
            run_id = uuid.uuid4().hex
            run_dir = data / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            output = run_dir / "output"
            direction = f"{evidence.language}-to-{target}"
            settings = {
                "retry_cap": MAX_RETRIES if evidence.scope_id == "project-editor" else 0,
                "token_budget": CONTEXT_TOKEN_BUDGET,
                "context_accounting": "whitespace_words_estimate",
                "generator": (
                    "openai-compatible-chat-v1"
                    if evidence.scope_id == "project-editor"
                    else "restricted-deterministic-translator-v1"
                ),
                "model": os.getenv("MIGRATION_MODEL", "none"),
                "prompt_version": EDITOR_PROMPT_VERSION if evidence.scope_id else "none",
                "max_completion_tokens": int(
                    os.getenv("MIGRATION_MAX_COMPLETION_TOKENS") or "6000"
                ),
                "arm_order": "graph_first" if reverse_order else "vector_first",
                "schema_version": 1,
                "parser_version": PARSER_VERSION,
                "embedding_version": evidence.preprocessing.embedding_model,
                "summary_model": evidence.preprocessing.summary_model,
                "preprocessing_ms": evidence.preprocessing.duration_ms,
                "preprocessing_summary_input_tokens": (evidence.preprocessing.summary_input_tokens),
                "preprocessing_summary_output_tokens": (
                    evidence.preprocessing.summary_output_tokens
                ),
                "preprocessing_embedding_tokens": evidence.preprocessing.embedding_input_tokens,
                "typescript_version": _tool_version("tsc", "--version"),
                "node_version": _tool_version("node", "--version"),
                "python_version": _tool_version("python", "--version"),
            }
            if evidence.scope_id:
                settings["scope_id"] = evidence.scope_id
            if evidence.source_commit:
                settings["source_commit"] = evidence.source_commit
            if evidence.preprocessing.cost_usd is not None:
                settings["preprocessing_cost_usd"] = evidence.preprocessing.cost_usd
            manifest = RunManifest(
                run_id=run_id,
                pair_id=pair_id,
                project_id=project.project_id,
                revision=project.revision,
                direction=direction,
                memory=arm,
                status="running",
                settings=settings,
            )
            manifest_path = run_dir / "manifest.json"
            manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            row = {
                "run_id": run_id,
                "pair_id": pair_id,
                "project_id": project.project_id,
                "revision": project.revision,
                "direction": direction,
                "memory": arm,
                "status": "running",
                "run_path": str(run_dir),
            }
            cat.record_run(row)
            if evidence.scope_id:
                scoped_files = [
                    {"path": path, "role": role}
                    for path, role in sorted(
                        {
                            (entity.path, entity.role)
                            for entity in evidence.entities
                            if entity.kind in {"module", "manifest"}
                        }
                    )
                ]
                (run_dir / "scoped_files.json").write_text(
                    json.dumps(scoped_files, indent=2), encoding="utf-8"
                )
            started = time.perf_counter()
            status = "failed"
            store = None
            try:
                store = (
                    VectorMemory(run_dir / "vector.jsonl", run_id, os.getenv("QDRANT_URL"))
                    if arm == "vector"
                    else GraphMemory(run_dir / "graph.jsonl", run_id, os.getenv("FALKORDB_HOST"))
                )
                outcome = run_workflow(
                    evidence, target, store, output, run_id, Path(project.cache_path)
                )
                (run_dir / "context_pack.json").write_text(
                    outcome.pack.model_dump_json(indent=2), encoding="utf-8"
                )
                (run_dir / "tasks.json").write_text(
                    json.dumps([task.model_dump() for task in outcome.tasks], indent=2),
                    encoding="utf-8",
                )
                (run_dir / "retrieved_evidence.json").write_text(
                    json.dumps(sorted(set(outcome.retrieved_ids)), indent=2), encoding="utf-8"
                )
                (run_dir / "validation.json").write_text(
                    outcome.validation.model_dump_json(indent=2), encoding="utf-8"
                )
                (run_dir / "model_responses.jsonl").write_text(
                    "".join(g.model_dump_json() + "\n" for g in outcome.generations),
                    encoding="utf-8",
                )
                status = "complete" if outcome.validation.passed else "failed"
                costs = [g.cost_usd for g in outcome.generations]
                write_event(
                    run_dir,
                    run_id,
                    "migrate",
                    "run_finished",
                    started,
                    validation_passed=outcome.validation.passed,
                    entity_count=len(evidence.entities),
                    task_count=len(outcome.tasks),
                    retries=outcome.retries,
                    input_tokens=sum(g.prompt_tokens for g in outcome.generations),
                    output_tokens=sum(g.completion_tokens for g in outcome.generations),
                    token_accounting="provider_usage" if outcome.generations else "none",
                    cost=sum(costs) if costs and all(c is not None for c in costs) else None,
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:1000]}"
                (run_dir / "validation.json").write_text(
                    ValidationResult(
                        passed=False,
                        checks={"syntax_or_compile": False, "behavioral": False},
                        output=error,
                    ).model_dump_json(indent=2),
                    encoding="utf-8",
                )
                write_event(run_dir, run_id, "migrate", "run_failed", started, error=error)
            finally:
                if isinstance(store, VectorMemory):
                    for usage in store.embedding_usage:
                        write_event(
                            run_dir,
                            run_id,
                            "embedding",
                            "embedding",
                            input_tokens=usage.prompt_tokens,
                            duration_ms=usage.duration_ms,
                            model=usage.model,
                            cost=usage.cost_usd,
                        )
                manifest.status = status
                manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
                cat.record_run(row | {"status": status})
                if status != "complete":
                    failures += 1
                print(f"{arm} run {run_id}: {status}; output={output}")
        return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.source, args.revision, args.scope_file, args.profile)
    if args.command == "migrate":
        return _migrate(args.project, args.target, args.memory, args.repeat)
    data = _data_dir()
    with Catalog(data / "catalog" / "projects.duckdb") as cat:
        runs = cat.list_runs()
        if args.project:
            runs = [row for row in runs if row["project_id"] == args.project]
        report = evaluate(runs, data / "runs" / "evaluation")
    print(json.dumps(report, indent=2))
    return 0


def _tool_version(executable: str, argument: str) -> str:
    import shutil

    if not shutil.which(executable):
        return "unavailable"
    result = subprocess.run([executable, argument], capture_output=True, text=True, timeout=10)
    return (result.stdout or result.stderr).strip().splitlines()[0]


if __name__ == "__main__":
    raise SystemExit(main())
