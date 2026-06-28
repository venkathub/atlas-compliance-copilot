"""Unit tests for the cost-regression gate (P6 Task 5)."""

import json

from atlas_evals.cost_gate import GATEWAY_BASELINE, evaluate_cost_gate, main


def _baseline(**overrides):
    base = {
        "cost_off_units": 20.0,
        "cost_on_units": 0.0,
        "cost_reduction_pct": 100.0,
        "target_reduction_pct": 30.0,
        "meets_target": True,
    }
    base.update(overrides)
    return base


def test_passes_when_reduction_meets_target():
    result = evaluate_cost_gate(_baseline())
    assert result.passed
    assert result.failures == []


def test_fails_when_reduction_below_target():
    result = evaluate_cost_gate(
        _baseline(cost_reduction_pct=12.0, meets_target=False)
    )
    assert not result.passed
    assert any("regressed below band" in f for f in result.failures)
    assert any("meets_target" in f for f in result.failures)


def test_fails_on_absolute_ceiling_even_when_reduction_holds():
    # Reduction still ≥ target, but absolute on-units blew past an explicit ceiling.
    result = evaluate_cost_gate(
        _baseline(cost_reduction_pct=40.0, cost_on_units=9.0, max_cost_on_units=5.0)
    )
    assert not result.passed
    assert any("absolute cost regression" in f for f in result.failures)


def test_fails_on_missing_fields():
    result = evaluate_cost_gate({"meets_target": True})
    assert not result.passed
    assert any("missing" in f for f in result.failures)


def test_passes_under_ceiling():
    result = evaluate_cost_gate(
        _baseline(cost_reduction_pct=40.0, cost_on_units=3.0, max_cost_on_units=5.0)
    )
    assert result.passed


def test_committed_gateway_baseline_passes_the_gate():
    # The real committed evidence must pass (guards against committing a regressed artifact).
    cost = json.loads(GATEWAY_BASELINE.read_text())
    assert evaluate_cost_gate(cost).passed


def test_cli_returns_zero_on_committed_baseline():
    assert main([]) == 0
