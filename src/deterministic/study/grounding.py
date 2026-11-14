"""Deterministic, evidence-only grounding check for the opaque study answers."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from deterministic.memory.base import Context, Record
from deterministic.study.scenario import StudyTask


class GroundingJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    status: Literal["supported", "unsupported", "abstained"]
    reason: Literal[
        "path_verified", "direct_statement", "missing_evidence", "contradicted", "abstention"
    ]
    supporting_ids: list[str]


def _edge(records: dict[str, Record], source: str, target: str) -> Record | None:
    return next(
        (
            record
            for record in records.values()
            if record.metadata.get("kind") == "relation"
            and record.metadata.get("relation") == "DEPENDS_ON"
            and record.metadata.get("source_id") == source
            and record.metadata.get("target_id") == target
        ),
        None,
    )


def judge_grounding(task: StudyTask, context: Context, answer: str) -> GroundingJudgment:
    """Judge only the supplied context; never inspect the hidden expected answer."""
    if answer == "UNKNOWN":
        return GroundingJudgment(status="abstained", reason="abstention", supporting_ids=[])
    records = {record.record_id: record for record in context.records}
    route = records.get(task.anchor_id)
    if route is None:
        return GroundingJudgment(status="unsupported", reason="missing_evidence", supporting_ids=[])
    handler_match = re.search(r"\bdelegates to handler (HD-[A-F0-9]{8})\b", route.content)
    if handler_match is None:
        return GroundingJudgment(status="unsupported", reason="missing_evidence", supporting_ids=[])
    handler_id = handler_match.group(1)
    if task.kind == "local":
        if answer == handler_id:
            return GroundingJudgment(
                status="supported", reason="direct_statement", supporting_ids=[route.record_id]
            )
        return GroundingJudgment(
            status="unsupported", reason="contradicted", supporting_ids=[route.record_id]
        )
    handler = records.get(f"handler:{handler_id}")
    first_edge = _edge(records, route.record_id, f"handler:{handler_id}")
    if handler is None or first_edge is None:
        return GroundingJudgment(
            status="unsupported", reason="missing_evidence", supporting_ids=[route.record_id]
        )
    contract_match = re.search(r"\busing contract (CT-[A-F0-9]{8})\b", handler.content)
    if contract_match is None:
        return GroundingJudgment(
            status="unsupported", reason="missing_evidence", supporting_ids=[route.record_id]
        )
    contract_id = contract_match.group(1)
    contract = records.get(f"contract:{contract_id}")
    second_edge = _edge(records, handler.record_id, f"contract:{contract_id}")
    if contract is None or second_edge is None:
        return GroundingJudgment(
            status="unsupported",
            reason="missing_evidence",
            supporting_ids=[route.record_id, first_edge.record_id, handler.record_id],
        )
    path = [route.record_id, first_edge.record_id, handler.record_id, second_edge.record_id]
    token_match = re.search(r"\bstatus token (ZX-[A-F0-9]{8})\b", contract.content)
    if token_match is None:
        return GroundingJudgment(
            status="unsupported", reason="missing_evidence", supporting_ids=path
        )
    path.append(contract.record_id)
    if answer == token_match.group(1):
        return GroundingJudgment(status="supported", reason="path_verified", supporting_ids=path)
    return GroundingJudgment(status="unsupported", reason="contradicted", supporting_ids=path)
