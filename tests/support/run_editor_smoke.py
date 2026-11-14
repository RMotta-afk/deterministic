"""Exercise the full paired pipeline with a fixed mock chat response inside Docker.

The response is a reference implementation, so this is an integration check,
not research evidence about either retrieval strategy.
"""

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deterministic.cli import main
from deterministic.ingestion.cache import _embedding

REFERENCE = Path("/support/editor_reference.ts").read_text(encoding="utf-8")


class MockChat(BaseHTTPRequestHandler):
    generation_count = 0

    def log_message(self, *_args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/embeddings":
            data = json.dumps(
                {
                    "model": request["model"],
                    "data": [{"embedding": _embedding(request["input"])}],
                    "usage": {"prompt_tokens": 20, "total_tokens": 20},
                }
            ).encode("utf-8")
        else:
            assert self.path == "/v1/chat/completions"
            if request["model"] == "editor-summary-mock":
                source = request["messages"][1]["content"]
                path = source.splitlines()[0]
                content = f"Summary of {path}: project editor API and contracts. " + source[0:200]
            else:
                assert request["model"] == "editor-reference-mock"
                MockChat.generation_count += 1
                content = "const broken =" if MockChat.generation_count % 2 else REFERENCE
            data = json.dumps(
                {
                    "model": request["model"],
                    "choices": [{"message": {"content": content}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                }
            ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run():
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["DETERMINISTIC_DATA_DIR"] = temp
            os.environ["MIGRATION_API_KEY"] = "mock-key"
            os.environ["MIGRATION_MODEL"] = "editor-reference-mock"
            os.environ["MIGRATION_SUMMARY_MODEL"] = "editor-summary-mock"
            os.environ["MIGRATION_EMBEDDING_MODEL"] = "editor-embedding-mock"
            os.environ["MIGRATION_INPUT_USD_PER_MILLION"] = "1"
            os.environ["MIGRATION_OUTPUT_USD_PER_MILLION"] = "2"
            os.environ["MIGRATION_EMBEDDING_USD_PER_MILLION"] = "0.1"
            os.environ["MIGRATION_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
            ingest_args = [
                "ingest",
                "/fixtures/project-editor",
                "--scope-file",
                "/fixtures/benchmark-scope.json",
                "--profile",
                "project-editor",
            ]
            assert main(ingest_args) == 0
            assert main(ingest_args) == 0
            ingest_manifests = list((Path(temp) / "runs").glob("ingest-*/manifest.json"))
            assert sorted(
                json.loads(path.read_text(encoding="utf-8"))["cache_hit"]
                for path in ingest_manifests
            ) == [False, True]
            from deterministic.catalog import Catalog

            with Catalog(Path(temp) / "catalog" / "projects.duckdb") as catalog:
                project_id = catalog.list_ready_projects()[0].project_id
            result = main(["migrate", "--project", project_id, "--memory", "both", "--repeat", "2"])
            with Catalog(Path(temp) / "catalog" / "projects.duckdb") as catalog:
                runs = catalog.list_runs()
            print(f"paired_smoke exit={result} runs={len(runs)}")
            for row in runs:
                validation = json.loads(
                    (Path(row["run_path"]) / "validation.json").read_text(encoding="utf-8")
                )
                print(
                    f"{row['memory']} status={row['status']} "
                    f"contracts={sum(validation['checks'].values()) - 2}"
                )
                from deterministic.memory.base import Request
                from deterministic.memory.graph_memory import GraphMemory
                from deterministic.memory.vector_memory import VectorMemory

                path = Path(row["run_path"])
                memory = (
                    VectorMemory(path / "vector.jsonl", row["run_id"], os.environ["QDRANT_URL"])
                    if row["memory"] == "vector"
                    else GraphMemory(
                        path / "graph.jsonl", row["run_id"], os.environ["FALKORDB_HOST"]
                    )
                )
                if row["memory"] == "graph":
                    from falkordb import FalkorDB

                    graph = FalkorDB(host=os.environ["FALKORDB_HOST"]).select_graph(row["run_id"])
                    edge_count = graph.ro_query(
                        "MATCH ()-[r:IMPORTS]->() RETURN count(r)"
                    ).result_set[0][0]
                    assert edge_count >= 5, f"expected source import edges, got {edge_count}"
                    for edge_type in ("USES_EVIDENCE", "PRODUCED_BY", "VALIDATES", "SUPERSEDES"):
                        count = graph.ro_query(
                            f"MATCH ()-[r:{edge_type}]->() RETURN count(r)"
                        ).result_set[0][0]
                        assert count > 0, f"expected runtime {edge_type} edges"
                records = [
                    json.loads(line)
                    for line in (path / f"{row['memory']}.jsonl").read_text().splitlines()
                ]
                assert {"artifact:0:0", "artifact:0:1"} <= {
                    record["record_id"] for record in records
                }
                feedback = memory.retrieve_context(
                    Request(query="validation feedback", token_budget=4000, limit=50)
                )
                assert any(
                    record.metadata.get("kind") == "validation" for record in feedback.records
                )
            assert result == 0
            assert len(runs) == 4 and all(row["status"] == "complete" for row in runs)
            from deterministic.telemetry.evaluator import evaluate

            assert evaluate(runs, Path(temp) / "runs" / "evaluation")
            report = json.loads(
                (Path(temp) / "runs" / "evaluation" / "evaluation.json").read_text(encoding="utf-8")
            )
            assert len(report["pairs"]) == 2
            assert all(item["validation_passed"] for item in report["runs"])
            assert all(item["retries"] == 1 for item in report["runs"])
            assert all(item["shared_preprocessing_tokens"] > 0 for item in report["runs"])
            vector = next(item for item in report["runs"] if item["memory"] == "vector")
            assert vector["runtime_embedding_tokens"] > 0
            rates = report["success_rate_by_memory"]
            print(
                f"pairs={len(report['pairs'])} vector_success={rates['vector']} "
                f"graph_success={rates['graph']}"
            )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run()
