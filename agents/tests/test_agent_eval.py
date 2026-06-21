"""Tests for the agent eval set + the merge-blocking gate (P4_SPEC §4.4–4.5)."""

from app.eval.agent_gate import evaluate_agent_gate, load_thresholds, main
from app.eval.agent_scorer import ScenarioResult, ScoreReport, score_all, score_scenario
from app.eval.scenarios import SCENARIOS


def _perfect(name="s"):
    return ScenarioResult(
        name=name,
        task_success=True,
        tool_selection_correct=True,
        argument_correct=True,
        step_efficient=True,
        plan_adhered=True,
        hitl_respected=True,
        authorization_respected=True,
    )


THRESHOLDS = {
    "task_success_floor": 0.80,
    "tool_selection_floor": 0.90,
    "argument_correctness_floor": 0.90,
    "plan_adherence_floor": 0.95,
}


def test_scenario_set_is_versioned_and_sized():
    assert len(SCENARIOS) >= 10
    assert len({s.name for s in SCENARIOS}) == len(SCENARIOS)  # unique names


def test_every_scenario_meets_its_expected_outcome():
    report = score_all()
    failing = [r.name for r in report.results if not r.task_success]
    assert failing == [], f"scenarios not matching expected outcome: {failing}"


def test_hard_gates_hold_across_all_scenarios():
    report = score_all()
    assert report.hitl_respected_all()
    assert report.authorization_respected_all()
    assert report.unapproved_writes() == 0
    assert report.unauthorized_writes() == 0


def test_forcing_story_writes_grounded_draft():
    forcing = next(s for s in SCENARIOS if s.name == "forcing_story_breach_approved")
    result = score_scenario(forcing)
    assert result.task_success
    assert result.argument_correct


def test_gate_passes_on_committed_scenarios():
    report = score_all()
    result = evaluate_agent_gate(report, load_thresholds())
    assert result.passed, result.failures


def test_gate_fails_on_an_unapproved_write():
    bad = _perfect("leak")
    bad.hitl_respected = False
    report = ScoreReport(results=[_perfect(), bad])
    result = evaluate_agent_gate(report, THRESHOLDS)
    assert not result.passed
    assert any("HITL" in f for f in result.failures)


def test_gate_fails_below_task_success_floor():
    failing = ScenarioResult("x", False, True, True, True, True, True, True)
    report = ScoreReport(results=[_perfect(), failing])
    # 50% task success < 0.80 floor.
    result = evaluate_agent_gate(report, THRESHOLDS)
    assert not result.passed
    assert any("task success" in f for f in result.failures)


def test_gate_cli_exits_zero():
    assert main([]) == 0
