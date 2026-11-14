"""Predeclared opaque dependency tasks and shared evidence records."""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from deterministic.memory.base import Record


class _Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DependencyChain(_Boundary):
    route: str = Field(pattern=r"^RT-[A-F0-9]{8}$")
    handler: str = Field(pattern=r"^HD-[A-F0-9]{8}$")
    contract: str = Field(pattern=r"^CT-[A-F0-9]{8}$")
    token: str = Field(pattern=r"^ZX-[A-F0-9]{8}$")


class StudyQuestion(_Boundary):
    chain_index: int = Field(ge=0)
    kind: Literal["local", "relational"]


class StudyTask(_Boundary):
    schema_version: Literal[1] = 1
    step: int = Field(ge=0)
    kind: Literal["local", "relational"]
    query: str
    anchor_id: str
    expected_answer: str
    expected_evidence_ids: list[str]
    previous_validation_id: str | None = None


class StudyScenario(_Boundary):
    schema_version: Literal[1] = 1
    scenario_id: str = Field(min_length=1)
    description: str
    chains: list[DependencyChain] = Field(min_length=4)
    questions: list[StudyQuestion] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_questions(self) -> "StudyScenario":
        indexes = [question.chain_index for question in self.questions]
        if len(set(indexes)) != len(indexes) or any(index >= len(self.chains) for index in indexes):
            raise ValueError("questions must refer to distinct existing chains")
        if not {question.kind for question in self.questions} == {"local", "relational"}:
            raise ValueError("scenario needs local and relational controls")
        return self

    @classmethod
    def from_file(cls, path: Path) -> "StudyScenario":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def task(self, step: int) -> StudyTask:
        question = self.questions[step]
        chain = self.chains[question.chain_index]
        route_id = f"route:{chain.route}"
        handler_id = f"handler:{chain.handler}"
        contract_id = f"contract:{chain.contract}"
        first_edge = f"edge:{chain.route}:{chain.handler}"
        second_edge = f"edge:{chain.handler}:{chain.contract}"
        if question.kind == "local":
            query = f"Which handler does route {chain.route} delegate to? Reply with its ID only."
            expected = chain.handler
            relevant = [route_id, first_edge, handler_id]
        else:
            query = (
                f"For route {chain.route}, which opaque response status token does its "
                "delegated contract define? Reply with the token only."
            )
            expected = chain.token
            relevant = [route_id, first_edge, handler_id, second_edge, contract_id]
        if step:
            query += f" Also report whether the reviewer of step {step - 1} passed or failed."
        return StudyTask(
            step=step,
            kind=question.kind,
            query=query,
            anchor_id=route_id,
            expected_answer=expected,
            expected_evidence_ids=relevant,
            previous_validation_id=f"study:validation:{step - 1}" if step else None,
        )

    def records(self, embed: Callable[[str], list[float]]) -> list[Record]:
        records = []
        for index, chain in enumerate(self.chains):
            provenance = [f"{self.scenario_id}:chain:{index}"]

            def add(
                record_id: str,
                content: str,
                metadata: dict[str, str],
                record_provenance: list[str] = provenance,
            ) -> None:
                records.append(
                    Record(
                        record_id=record_id,
                        content=content,
                        provenance=record_provenance,
                        metadata=metadata,
                        vector=embed(content),
                    )
                )

            add(
                f"route:{chain.route}",
                f"Route {chain.route} is an /api/projects integration entry point. "
                f"It delegates to handler {chain.handler}.",
                {"kind": "module", "role": "route"},
            )
            add(
                f"handler:{chain.handler}",
                f"Handler {chain.handler} transforms requests using contract {chain.contract}.",
                {"kind": "module", "role": "handler"},
            )
            add(
                f"contract:{chain.contract}",
                f"Contract {chain.contract} defines opaque response status token {chain.token}.",
                {"kind": "module", "role": "contract"},
            )
            add(
                f"edge:{chain.route}:{chain.handler}",
                f"Route {chain.route} DEPENDS_ON handler {chain.handler}.",
                {
                    "kind": "relation",
                    "relation": "DEPENDS_ON",
                    "source_id": f"route:{chain.route}",
                    "target_id": f"handler:{chain.handler}",
                },
            )
            add(
                f"edge:{chain.handler}:{chain.contract}",
                f"Handler {chain.handler} DEPENDS_ON contract {chain.contract}.",
                {
                    "kind": "relation",
                    "relation": "DEPENDS_ON",
                    "source_id": f"handler:{chain.handler}",
                    "target_id": f"contract:{chain.contract}",
                },
            )
        return records
