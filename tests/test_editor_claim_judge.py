"""The independent claim audit must cover the full frozen rubric."""

import pytest
from pydantic import ValidationError

from deterministic.agents.model import ModelResult
from deterministic.agents.validator import ValidationResult
from deterministic.telemetry.editor_claim_judge import (
    CALIBRATION_CHECKS,
    CLAIMS,
    ClaimAudit,
    ClaimFinding,
    ClaimPayload,
    assess_calibration,
    calibrate,
)


def test_claim_audit_rejects_omissions_and_duplicate_ids():
    items = [
        {"id": claim_id, "verdict": "uncertain", "code_evidence": "", "reason": "not proven"}
        for claim_id in CLAIMS
    ]
    assert len(ClaimPayload.model_validate({"findings": items}).findings) == 12
    with pytest.raises(ValidationError):
        ClaimPayload.model_validate({"findings": items[:-1]})
    with pytest.raises(ValidationError):
        ClaimPayload.model_validate({"findings": items[:-1] + [items[0]]})


def test_calibration_rejects_judge_false_positive_and_inexact_quote(tmp_path):
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "server.ts").write_text("const real = true;", encoding="utf-8")
    audit = ClaimAudit(
        run_id=tmp_path.name,
        contract_sha256="contract",
        artifact_sha256="artifact",
        prompt_version="prompt",
        response=ModelResult(
            text="{}", model="mock", prompt_tokens=0, completion_tokens=0, duration_ms=0
        ),
        findings=[
            ClaimFinding(
                id=claim_id,
                verdict="supported",
                code_evidence="not in code" if claim_id == "routes" else "",
                reason="claimed support",
            )
            for claim_id in CLAIMS
        ],
        supported=len(CLAIMS),
        contradicted=0,
        uncertain=0,
        contradiction_rate=0,
    )
    (tmp_path / "claim_audit.json").write_text(audit.model_dump_json(), encoding="utf-8")
    checks = {check: True for group in CALIBRATION_CHECKS.values() for check in group}
    checks["validation_422"] = False
    validation = ValidationResult(passed=False, checks=checks, output="validation_422 failed")
    (tmp_path / "validation.json").write_text(validation.model_dump_json(), encoding="utf-8")
    result = calibrate(tmp_path)
    assert not result.passed
    assert result.false_supports == ["validation_422"]
    assert result.inexact_code_quotes == ["routes"]
    assert assess_calibration(tmp_path) == result
