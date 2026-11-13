"""Command-line entry point for the three strict pipeline stages."""

from __future__ import annotations

import argparse
import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from deterministic.catalog import Catalog, Project
from deterministic.ingestion.repo_loader import load_source


class IngestRequest(BaseModel):
    """Validated input crossing from CLI parsing into ingestion."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source: str = Field(min_length=1)
    data_dir: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deterministic",
        description="Ingest, migrate, and evaluate paired memory experiments.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Index a pinned repository or local fixture")
    ingest.add_argument("source", help="Repository URL or local path")

    migrate = commands.add_parser("migrate", help="Migrate an indexed project")
    migrate.add_argument("--project", help="Indexed project ID (omit to choose interactively)")
    migrate.add_argument("--target", choices=("python", "typescript"))
    migrate.add_argument("--memory", choices=("vector", "graph", "both"), default="both")

    commands.add_parser("evaluate", help="Evaluate recorded runs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        request = IngestRequest.model_validate(
            {
                "source": args.source,
                "data_dir": Path(os.environ.get("DETERMINISTIC_DATA_DIR", "data")),
            }
        )
        snapshot = load_source(request.source, request.data_dir / "cache" / "sources")
        project_id = hashlib.sha256(f"{request.source}\0{snapshot.revision}".encode()).hexdigest()[
            :16
        ]
        with Catalog(request.data_dir / "catalog" / "projects.duckdb") as catalog:
            catalog.upsert_project(
                Project(
                    project_id=project_id,
                    source=snapshot.source,
                    revision=snapshot.revision,
                    language="pending",
                    cache_path=str(snapshot.path),
                    status="ingesting",
                )
            )
        print(f"Source snapshot cached: {project_id} ({snapshot.revision})")
        print("Parsing and embeddings are pending; this project is not ready to migrate.")
        return 2
    parser.error(f"{args.command} is planned but not implemented yet")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
