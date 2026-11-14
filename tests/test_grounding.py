"""The hallucination check uses evidence, not the hidden answer key."""

from pathlib import Path

from deterministic.memory.base import Context
from deterministic.study.grounding import judge_grounding
from deterministic.study.scenario import StudyScenario

SCENARIO = Path(__file__).parents[1] / "fixtures/long-horizon.json"


def _context(records):
    return Context(records=records, token_count=0, evidence_ids=[r.record_id for r in records])


def test_grounding_separates_abstention_false_claim_and_supported_claim():
    scenario = StudyScenario.from_file(SCENARIO)
    task = scenario.task(0)
    route = next(r for r in scenario.records(lambda _: [0.0]) if r.record_id == task.anchor_id)
    context = _context([route])
    assert judge_grounding(task, context, "UNKNOWN").status == "abstained"
    assert judge_grounding(task, context, task.expected_answer).status == "supported"
    wrong = judge_grounding(task, context, "HD-FFFFFFFF")
    assert wrong.status == "unsupported" and wrong.reason == "contradicted"


def test_two_hop_claim_requires_the_retrieved_path_and_verifies_its_token():
    scenario = StudyScenario.from_file(SCENARIO)
    task = scenario.task(1)
    relevant = [
        record
        for record in scenario.records(lambda _: [0.0])
        if record.record_id in task.expected_evidence_ids
    ]
    assert judge_grounding(task, _context(relevant), task.expected_answer).status == "supported"
    assert judge_grounding(task, _context(relevant), "ZX-FFFFFFFF").reason == "contradicted"
    without_second_edge = [r for r in relevant if r.record_id != task.expected_evidence_ids[3]]
    missing = judge_grounding(task, _context(without_second_edge), task.expected_answer)
    assert missing.status == "unsupported" and missing.reason == "missing_evidence"
    altered = [
        r.model_copy(update={"content": r.content.replace(task.expected_answer, "ZX-FFFFFFFF")})
        for r in relevant
    ]
    assert judge_grounding(task, _context(altered), "ZX-FFFFFFFF").status == "supported"
