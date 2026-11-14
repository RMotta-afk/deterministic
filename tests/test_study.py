"""The controlled study exercises delayed memory without answer leakage."""

from pathlib import Path

from deterministic.study.runner import (
    CONTEXT_WORD_BUDGET,
    StudyComparison,
    _candidate_from_handoff,
    run_session,
)
from deterministic.study.scenario import StudyScenario

SCENARIO = Path(__file__).parents[1] / "fixtures/long-horizon.json"


def test_gold_answers_are_absent_from_public_tasks():
    scenario = StudyScenario.from_file(SCENARIO)
    assert len(scenario.chains) == len(scenario.questions) == 12
    for index in range(len(scenario.questions)):
        task = scenario.task(index)
        assert task.expected_answer not in task.query
        assert task.anchor_id in task.expected_evidence_ids


def test_mock_study_scores_two_hop_retention_and_local_controls(tmp_path: Path):
    report, path = run_session(SCENARIO, "mock", "both", 1, tmp_path)
    saved = StudyComparison.model_validate_json(path.read_text(encoding="utf-8"))
    assert saved == report
    assert len(report.pairs) == 1 and len(report.runs) == 2
    graph = next(run for run in report.runs if run.memory == "graph")
    vector = next(run for run in report.runs if run.memory == "vector")
    assert all(step.passed for step in graph.steps)
    assert sum(step.passed for step in vector.steps if step.kind == "local") == 3
    assert sum(step.passed for step in vector.steps if step.kind == "relational") < 9
    assert all(
        step.context_words <= CONTEXT_WORD_BUDGET for run in report.runs for step in run.steps
    )
    assert graph.steps[-1].memory_records > graph.steps[0].memory_records
    assert all(step.evidence_recall == 1.0 for step in graph.steps)
    assert all(step.analyst_candidate_correct for step in graph.steps)
    assert graph.grounding_summary.assertive == 12
    assert graph.grounding_summary.unsupported == 0
    assert graph.grounding_summary.unsupported_assertion_rate == 0
    assert vector.grounding_summary.abstained > 0
    for run in (vector, graph):
        assert all(step.state_recalled for step in run.steps[1:])
        assert all(step.analyst_state_correct for step in run.steps[1:])
    assert (tmp_path / "cache" / "study").is_dir()


def test_no_memory_ablation_cannot_answer_opaque_tasks(tmp_path: Path):
    report, _ = run_session(SCENARIO, "mock", "none", 1, tmp_path)
    run = report.runs[0]
    assert run.status == "complete"
    assert all(not step.passed and step.evidence_recall == 0 for step in run.steps)
    assert all(step.answer == "UNKNOWN" for step in run.steps)
    assert run.grounding_summary.assertive == 0
    assert run.grounding_summary.unsupported_assertion_rate is None


def test_metadata_aware_vector_followups_challenge_graph_advantage(tmp_path: Path):
    report, _ = run_session(SCENARIO, "mock", "strong", 1, tmp_path)
    assert report.pairs[0]["vector_strategy"] == "vector_followup"
    assert all(run.status == "complete" for run in report.runs)
    assert all(step.passed for run in report.runs for step in run.steps)


def test_handoff_extraction_accepts_a_bare_candidate_but_not_a_state_line():
    assert _candidate_from_handoff("ZX-1E80BADC\nSTATE=passed", "relational") == "ZX-1E80BADC"
    assert _candidate_from_handoff("CANDIDATE=UNKNOWN\nSTATE=passed", "relational") == "UNKNOWN"


def test_previous_diagnostic_step_without_candidate_fields_is_valid():
    from deterministic.study.runner import StepObservation

    step = StepObservation.model_validate(
        {
            "step": 0,
            "kind": "local",
            "query": "example",
            "anchor_id": "route:example",
            "expected_answer": "HD-00000000",
            "answer": "UNKNOWN",
            "passed": False,
            "retrieved_ids": [],
            "expected_evidence_ids": ["route:example"],
            "previous_validation_id": None,
            "state_recalled": None,
            "analyst_state_correct": None,
            "evidence_recall": 0,
            "context_words": 0,
            "memory_records": 0,
            "retrieval_ms": 0,
            "analyst_input_tokens": 0,
            "analyst_output_tokens": 0,
            "builder_input_tokens": 0,
            "builder_output_tokens": 0,
            "end_to_end_ms": 0,
        }
    )
    assert step.analyst_candidate is None
    assert step.analyst_candidate_correct is None
