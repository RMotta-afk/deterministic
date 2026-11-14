"""Fail-closed, reproducible check of the TCC's four proposed metrics."""

import argparse
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deterministic.ingestion.schemas import Evidence
from deterministic.telemetry.editor_claim_judge import (
    ClaimAudit,
    ClaimCalibration,
    assess_calibration,
)
from deterministic.telemetry.evaluator import EvaluationReport, RunReport


class ArmObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    run_id: str
    memory: Literal["vector", "graph"]
    contract_checks_passed: int = Field(ge=0)
    contract_checks_total: int = Field(ge=0)
    validation_passed: bool
    latency_ms: float = Field(ge=0)
    retrieval_ms: float = Field(ge=0)
    chat_input_tokens: int = Field(ge=0)
    chat_output_tokens: int = Field(ge=0)
    runtime_embedding_tokens: int = Field(ge=0)
    runtime_provider_tokens: int = Field(ge=0)
    runtime_provider_cost_usd: float | None = Field(ge=0)
    path_evidence_recall: float | None = Field(ge=0, le=1)
    judge_raw_contradiction_rate: float | None = Field(ge=0, le=1)
    judge_calibration_passed: bool
    judge_false_supports: list[str]
    judge_inexact_quotes: list[str]


class TccObservabilityGate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    pair_id: str
    source_relation_count: int = Field(ge=0)
    shared_preprocessing_ms: float = Field(ge=0)
    shared_preprocessing_cost_usd: float | None = Field(ge=0)
    arms: list[ArmObservation]
    hallucination_status: Literal["partially_calibrated", "judge_failed_calibration"]
    relational_accuracy_status: Literal["validated", "not_measured"]
    latency_status: Literal["measured"]
    token_consumption_status: Literal["measured"]
    useful_context_ratio_status: Literal["measured", "not_measured"]
    all_four_tcc_metrics_validated: bool


def _arm(archive: Path, report: RunReport, contract_hash: str) -> ArmObservation:
    arm_path = archive / "arms" / report.run_id
    audit = ClaimAudit.model_validate_json(
        (arm_path / "claim_audit.json").read_text(encoding="utf-8")
    )
    calibration = ClaimCalibration.model_validate_json(
        (arm_path / "claim_calibration.json").read_text(encoding="utf-8")
    )
    if calibration != assess_calibration(arm_path):
        raise ValueError(f"Judge calibration does not match archived arm {report.run_id}")
    code_hash = hashlib.sha256((arm_path / "output" / "server.ts").read_bytes()).hexdigest()
    if (
        audit.run_id != report.run_id
        or calibration.run_id != report.run_id
        or audit.contract_sha256 != contract_hash
        or audit.artifact_sha256 != code_hash
    ):
        raise ValueError(f"Judge evidence does not match archived arm {report.run_id}")
    if report.validation_passed is None or report.memory not in {"vector", "graph"}:
        raise ValueError(f"Arm {report.run_id} lacks a complete outcome")
    return ArmObservation(
        run_id=report.run_id,
        memory=report.memory,
        contract_checks_passed=report.contract_checks_passed,
        contract_checks_total=report.contract_checks_total,
        validation_passed=report.validation_passed,
        latency_ms=report.end_to_end_ms,
        retrieval_ms=report.retrieval_ms,
        chat_input_tokens=report.input_tokens,
        chat_output_tokens=report.output_tokens,
        runtime_embedding_tokens=report.runtime_embedding_tokens,
        runtime_provider_tokens=(
            report.input_tokens + report.output_tokens + report.runtime_embedding_tokens
        ),
        runtime_provider_cost_usd=report.runtime_provider_cost_usd,
        path_evidence_recall=report.evidence_recall,
        judge_raw_contradiction_rate=audit.contradiction_rate,
        judge_calibration_passed=calibration.passed,
        judge_false_supports=calibration.false_supports,
        judge_inexact_quotes=calibration.inexact_code_quotes,
    )


def check_archive(archive: Path) -> TccObservabilityGate:
    report = EvaluationReport.model_validate_json(
        (archive / "pair_evaluation.json").read_text(encoding="utf-8")
    )
    evidence = Evidence.model_validate_json(
        (archive / "evidence_snapshot.json").read_text(encoding="utf-8")
    )
    contract_hash = hashlib.sha256((archive / "source-contract.md").read_bytes()).hexdigest()
    if len(report.pairs) != 1 or len(report.runs) != 2:
        raise ValueError("TCC gate requires exactly one vector/graph pair")
    pair = report.pairs[0]
    if (
        {run.memory for run in report.runs} != {"vector", "graph"}
        or any(run.pair_id != pair.pair_id for run in report.runs)
        or len({run.settings_signature for run in report.runs}) != 1
        or any(run.revision != evidence.revision for run in report.runs)
    ):
        raise ValueError("The paired arms do not share source and settings")
    arms = [_arm(archive, run, contract_hash) for run in report.runs]
    hallucination_valid = all(arm.judge_calibration_passed for arm in arms)
    result = TccObservabilityGate(
        pair_id=pair.pair_id,
        source_relation_count=len(evidence.relations),
        shared_preprocessing_ms=evidence.preprocessing.duration_ms,
        shared_preprocessing_cost_usd=evidence.preprocessing.cost_usd,
        arms=arms,
        hallucination_status=(
            "partially_calibrated" if hallucination_valid else "judge_failed_calibration"
        ),
        relational_accuracy_status="not_measured",
        latency_status="measured",
        token_consumption_status="measured",
        useful_context_ratio_status="not_measured",
        all_four_tcc_metrics_validated=False,
    )
    (archive / "observability_gate.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the TCC observability evidence package")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    result = check_archive(args.archive)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
