"""Isolated vector memory with optional Qdrant-compatible runtime endpoint."""

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from deterministic.agents.model import ChatModel, EmbeddingResult, ModelSettings
from deterministic.ingestion.cache import _embedding
from deterministic.memory.base import Context, MemoryAdapter, PersistResult, Record, Request


class VectorMemory(MemoryAdapter):
    def __init__(
        self,
        path: Path,
        collection: str,
        qdrant_url: str | None = None,
        use_provider_embeddings: bool = True,
    ):
        self.path, self.collection, self.qdrant_url = path, collection, qdrant_url
        self._collection_ready = False
        self.embedding_model = (
            os.getenv("MIGRATION_EMBEDDING_MODEL") if use_provider_embeddings else None
        )
        self.embedding_client = (
            ChatModel(ModelSettings.from_environment()) if self.embedding_model else None
        )
        self.embedding_usage: list[EmbeddingResult] = []
        path.parent.mkdir(parents=True, exist_ok=True)
        self.records = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                rec = Record.model_validate_json(line)
                self.records[rec.record_id] = rec

    def persist_artifact(self, record: Record) -> PersistResult:
        if not record.vector:
            record = record.model_copy(
                update={
                    "vector": self._embed(record.metadata.get("kind", "") + " " + record.content)
                }
            )
        self.records[record.record_id] = record
        self.path.write_text(
            "".join(r.model_dump_json() + "\n" for r in self.records.values()), encoding="utf-8"
        )
        if self.qdrant_url:
            self._ensure_collection(len(record.vector))
            payload = {
                "points": [
                    {
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, record.record_id)),
                        "vector": record.vector,
                        "payload": {
                            "content": record.content,
                            "record_id": record.record_id,
                            "provenance": record.provenance,
                            **record.metadata,
                        },
                    }
                ]
            }
            req = urllib.request.Request(
                self.qdrant_url.rstrip("/") + f"/collections/{self.collection}/points?wait=true",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(req, timeout=10).read()
        return PersistResult(record_id=record.record_id, persisted=True)

    def _ensure_collection(self, dimension: int) -> None:
        if self._collection_ready:
            return
        url = self.qdrant_url.rstrip("/") + f"/collections/{self.collection}"
        try:
            urllib.request.urlopen(url, timeout=5).read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            req = urllib.request.Request(
                url,
                data=json.dumps({"vectors": {"size": dimension, "distance": "Cosine"}}).encode(),
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(req, timeout=10).read()
        self._collection_ready = True

    def retrieve_context(self, request: Request) -> Context:
        if self.qdrant_url and self.records:
            query = {
                "query": self._embed(request.query),
                "limit": request.limit,
                "with_payload": True,
            }
            req = urllib.request.Request(
                self.qdrant_url.rstrip("/") + f"/collections/{self.collection}/points/query",
                data=json.dumps(query).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            response = json.loads(urllib.request.urlopen(req, timeout=10).read())
            points = response.get("result", {}).get("points", [])
            ranked = [
                self.records[p["payload"]["record_id"]]
                for p in points
                if p.get("payload", {}).get("record_id") in self.records
            ]
        else:
            ranked = sorted(
                self.records.values(), key=lambda r: self._score(request.query, r), reverse=True
            )
        anchors = [
            self.records[record_id] for record_id in request.anchor_ids if record_id in self.records
        ]
        ranked = list(dict.fromkeys(record.record_id for record in anchors + ranked))
        ranked = [self.records[record_id] for record_id in ranked]
        selected = []
        count = 0
        for rec in ranked[: request.limit]:
            cost = max(1, len(rec.content.split()))
            if count + cost <= request.token_budget:
                selected.append(rec)
                count += cost
        return Context(
            records=selected, token_count=count, evidence_ids=[r.record_id for r in selected]
        )

    def _embed(self, content: str) -> list[float]:
        if self.embedding_client and self.embedding_model:
            result = self.embedding_client.embed(content, self.embedding_model)
            self.embedding_usage.append(result)
            return result.vector
        return _embedding(content)

    @staticmethod
    def _score(query, rec):
        terms = set(query.lower().split())
        body = set(rec.content.lower().split())
        return len(terms & body) / (len(terms | body) or 1)


class FollowupVectorMemory(VectorMemory):
    """Vector search plus bounded exact-ID follow-ups from retrieved text pointers."""

    def _point(self, record_id: str) -> Record | None:
        if record_id not in self.records:
            return None
        if self.qdrant_url:
            point_id = uuid.uuid5(uuid.NAMESPACE_URL, record_id)
            url = self.qdrant_url.rstrip("/") + f"/collections/{self.collection}/points/{point_id}"
            try:
                response = json.loads(urllib.request.urlopen(url, timeout=10).read())
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                raise
            if response.get("result", {}).get("payload", {}).get("record_id") != record_id:
                return None
        return self.records[record_id]

    def retrieve_context(self, request: Request) -> Context:
        initial = super().retrieve_context(request)
        ordered: list[Record] = [
            record for record in initial.records if record.record_id in request.anchor_ids
        ]
        for anchor_id in request.anchor_ids:
            if not anchor_id.startswith("route:"):
                continue
            route = self._point(anchor_id)
            if route is None:
                continue
            handler_match = re.search(r"\bhandler (HD-[A-F0-9]{8})\b", route.content)
            if handler_match is None:
                continue
            handler_id = handler_match.group(1)
            handler = self._point(f"handler:{handler_id}")
            if handler is None:
                continue
            for record_id in (f"edge:{anchor_id.removeprefix('route:')}:{handler_id}",):
                if edge := self._point(record_id):
                    ordered.append(edge)
            ordered.append(handler)
            contract_match = re.search(r"\bcontract (CT-[A-F0-9]{8})\b", handler.content)
            if contract_match is None:
                continue
            contract_id = contract_match.group(1)
            if edge := self._point(f"edge:{handler_id}:{contract_id}"):
                ordered.append(edge)
            if contract := self._point(f"contract:{contract_id}"):
                ordered.append(contract)
        ordered.extend(initial.records)
        selected: list[Record] = []
        seen: set[str] = set()
        words = 0
        for record in ordered:
            if record.record_id in seen:
                continue
            seen.add(record.record_id)
            cost = max(1, len(record.content.split()))
            if words + cost <= request.token_budget:
                selected.append(record)
                words += cost
            if len(selected) >= request.limit:
                break
        return Context(
            records=selected, token_count=words, evidence_ids=[r.record_id for r in selected]
        )
