"""Run-isolated provenance graph memory with optional FalkorDB runtime endpoint."""

import os
from pathlib import Path

from deterministic.memory.base import Context, MemoryAdapter, PersistResult, Record, Request


class GraphMemory(MemoryAdapter):
    def __init__(self, path: Path, graph: str, endpoint: str | None = None):
        self.path, self.graph, self.endpoint = path, graph, endpoint
        path.parent.mkdir(parents=True, exist_ok=True)
        self.records = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                r = Record.model_validate_json(line)
                self.records[r.record_id] = r

    def persist_artifact(self, record: Record) -> PersistResult:
        self.records[record.record_id] = record
        self.path.write_text(
            "".join(r.model_dump_json() + "\n" for r in self.records.values()), encoding="utf-8"
        )
        if self.endpoint:
            from falkordb import FalkorDB

            graph = FalkorDB(
                host=self.endpoint,
                port=int(os.getenv("FALKORDB_PORT", "6379")),
            ).select_graph(self.graph)
            labels = {
                "relation": "Evidence",
                "task": "TaskNode",
                "artifact": "MigrationArtifact",
                "validation": "ValidationResult",
            }
            label = labels.get(record.metadata.get("kind", ""), "Evidence")
            graph.query(
                f"MERGE (n:{label} {{id:$id}}) SET n.content=$content, n.provenance=$provenance",
                params={
                    "id": record.record_id,
                    "content": record.content,
                    "provenance": record.provenance,
                },
            )
            if record.metadata.get("kind") == "relation":
                edge_type = record.metadata.get("relation", "DEPENDS_ON")
                if edge_type not in {
                    "IMPORTS",
                    "CALLS",
                    "INHERITS_FROM",
                    "IMPLEMENTS_CONTRACT",
                    "DEPENDS_ON",
                }:
                    edge_type = "DEPENDS_ON"
                graph.query(
                    f"MATCH (a:Evidence {{id:$source}}), (b:Evidence {{id:$target}}) "
                    f"MERGE (a)-[r:{edge_type} {{id:$id}}]->(b) "
                    "SET r.provenance=$provenance",
                    params={
                        "id": record.record_id,
                        "provenance": record.provenance,
                        "source": record.metadata["source_id"],
                        "target": record.metadata["target_id"],
                    },
                )
        return PersistResult(record_id=record.record_id, persisted=True)

    def retrieve_context(self, request: Request) -> Context:
        terms = set(request.query.lower().split())
        neighbors: dict[str, list[str]] = {}
        if self.endpoint:
            from falkordb import FalkorDB

            graph = FalkorDB(
                host=self.endpoint,
                port=int(os.getenv("FALKORDB_PORT", "6379")),
            ).select_graph(self.graph)
            rows = graph.ro_query(
                "MATCH (a:Evidence)-[r]->(b:Evidence) RETURN a.id, b.id LIMIT 500"
            ).result_set
            for source_id, target_id in rows:
                neighbors.setdefault(str(source_id), []).append(str(target_id))
            stored_ids = set(self.records)
            if self.endpoint:
                stored_ids = {
                    str(row[0])
                    for row in graph.ro_query("MATCH (n) RETURN n.id LIMIT 5000").result_set
                }
        else:
            stored_ids = set(self.records)
        ranked = sorted(
            (record for record in self.records.values() if record.record_id in stored_ids),
            key=lambda r: len(
                terms & set((r.metadata.get("kind", "") + " " + r.content).lower().split())
            ),
            reverse=True,
        )
        result = []
        used = set()
        count = 0
        seed_ids = [record.record_id for record in ranked[: request.limit]]
        traversal_ids = list(seed_ids)
        for record_id in seed_ids:
            traversal_ids.extend(neighbors.get(record_id, [])[: request.limit])
        ordered = [
            self.records[record_id]
            for record_id in dict.fromkeys(traversal_ids)
            if record_id in self.records
        ]
        for rec in ordered:
            related = bool(used.intersection(rec.provenance))
            cost = max(1, len(rec.content.split()))
            if (
                not result
                or related
                or terms.intersection(
                    (rec.metadata.get("kind", "") + " " + rec.content).lower().split()
                )
            ) and count + cost <= request.token_budget:
                result.append(rec)
                used.update(rec.provenance)
                count += cost
            if len(result) >= request.limit:
                break
        return Context(
            records=result, token_count=count, evidence_ids=[r.record_id for r in result]
        )
