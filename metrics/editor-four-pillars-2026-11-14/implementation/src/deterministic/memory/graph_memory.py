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
                    "USES_EVIDENCE",
                    "PRODUCED_BY",
                    "VALIDATES",
                    "SUPERSEDES",
                }:
                    edge_type = "DEPENDS_ON"
                graph.query(
                    "MATCH (a {id:$source}), (b {id:$target}) "
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
        candidates = [
            record for record in self.records.values() if record.metadata.get("kind") != "relation"
        ]

        def score(record: Record) -> int:
            return len(
                terms
                & set((record.metadata.get("kind", "") + " " + record.content).lower().split())
            )

        ranked = sorted(candidates, key=lambda record: (-score(record), record.record_id))
        anchors = [record_id for record_id in request.anchor_ids if record_id in self.records]
        seeds = list(
            dict.fromkeys(
                anchors or [record.record_id for record in ranked if score(record) > 0][:3]
            )
        )
        if not seeds and ranked:
            seeds = [ranked[0].record_id]
        ordered_ids = list(seeds)
        visited = set(seeds)
        frontier = seeds
        for _depth in range(2):
            next_frontier = []
            for record_id in frontier:
                for neighbor_id, edge_id in self._neighbors(record_id, request.limit):
                    if edge_id in self.records and edge_id not in ordered_ids:
                        ordered_ids.append(edge_id)
                    if neighbor_id in self.records and neighbor_id not in visited:
                        ordered_ids.append(neighbor_id)
                        visited.add(neighbor_id)
                        next_frontier.append(neighbor_id)
                    if len(visited) >= request.limit:
                        break
                if len(visited) >= request.limit:
                    break
            frontier = next_frontier
            if not frontier or len(visited) >= request.limit:
                break
        result: list[Record] = []
        count = 0
        for record_id in ordered_ids:
            rec = self.records[record_id]
            cost = max(1, len(rec.content.split()))
            if count + cost <= request.token_budget:
                result.append(rec)
                count += cost
            if len(result) >= request.limit:
                break
        return Context(
            records=result, token_count=count, evidence_ids=[r.record_id for r in result]
        )

    def _neighbors(self, record_id: str, limit: int) -> list[tuple[str, str]]:
        if self.endpoint:
            from falkordb import FalkorDB

            graph = FalkorDB(
                host=self.endpoint,
                port=int(os.getenv("FALKORDB_PORT", "6379")),
            ).select_graph(self.graph)
            rows = graph.ro_query(
                f"MATCH (a {{id:$id}})-[r]-(b) RETURN b.id, r.id ORDER BY b.id LIMIT {limit}",
                params={"id": record_id},
            ).result_set
            return [(str(neighbor), str(edge)) for neighbor, edge in rows]
        neighbors = []
        for record in self.records.values():
            if record.metadata.get("kind") != "relation":
                continue
            source = record.metadata.get("source_id")
            target = record.metadata.get("target_id")
            if source == record_id and target:
                neighbors.append((target, record.record_id))
            elif target == record_id and source:
                neighbors.append((source, record.record_id))
        return sorted(neighbors)[:limit]
