"""Unit tests for the GPU-free model-promotion gate (P7 Task 2)."""

import json

from atlas_evals.promotion_floors import load_floors
from atlas_evals.promotion_gate import (
    evaluate_promotion_gate,
    main,
    write_report,
)

FLOORS = load_floors()  # committed promotion-floors.json (hybrid, floors 0.656 / 0.95)


def _comparison(*, faith=(0.787, 0.678), fmt=(0.0, 0.955), refusal=(0.375, 0.375), cost=None):
    def block(pair):
        return {"base": pair[0], "ft": pair[1], "delta": round(pair[1] - pair[0], 4)}

    comp = {
        "metrics": {
            "faithfulness": block(faith),
            "format_validity": block(fmt),
            "refusal_correctness": block(refusal),
        },
        "model_ids": {"base": "Qwen/Qwen2.5-7B-Instruct", "ft": "hf://acme/adapter@abc"},
        "git_sha": "deadbeef",
    }
    if cost is not None:
        comp["cost"] = cost
    return comp


# ---- the real P6 adapter is the committed "promoted" example (ADR-0076) ----
def test_real_adapter_promotes_via_hybrid_format_jump():
    # faithfulness regressed -0.109 (beyond 0.05 band) BUT above floor AND format jumped 0->0.955.
    result = evaluate_promotion_gate(_comparison(), FLOORS)
    assert result.promoted
    assert result.blocked_reasons == []
    assert result.model_version == "hf://acme/adapter@abc"


def test_block_when_faithfulness_below_floor():
    result = evaluate_promotion_gate(_comparison(faith=(0.787, 0.600)), FLOORS)
    assert not result.promoted
    assert any("below floor" in r for r in result.blocked_reasons)


def test_block_when_format_below_floor():
    result = evaluate_promotion_gate(_comparison(fmt=(0.0, 0.90)), FLOORS)
    assert not result.promoted
    assert any("format_validity" in r for r in result.blocked_reasons)


def test_block_when_refusal_regresses():
    result = evaluate_promotion_gate(_comparison(refusal=(0.500, 0.375)), FLOORS)
    assert not result.promoted
    assert any("refusal_correctness" in r for r in result.blocked_reasons)


def test_block_when_format_flat_and_faithfulness_regressed():
    # format did NOT jump (already high, no delta) AND faithfulness regressed beyond band -> block.
    result = evaluate_promotion_gate(_comparison(faith=(0.900, 0.700), fmt=(0.96, 0.96)), FLOORS)
    assert not result.promoted
    assert any("format did not jump" in r for r in result.blocked_reasons)


def test_promote_when_within_band_and_format_flat():
    # faithfulness within the 0.05 band, format already above floor and flat -> the band branch
    # promotes even without a jump.
    result = evaluate_promotion_gate(_comparison(faith=(0.800, 0.780), fmt=(0.96, 0.96)), FLOORS)
    assert result.promoted


def test_block_on_cost_regression_when_measured():
    result = evaluate_promotion_gate(
        _comparison(cost={"delta_pct": 25.0, "same_gpu": "L4"}), FLOORS
    )
    assert not result.promoted
    assert any("cost/request regressed" in r for r in result.blocked_reasons)


def test_promote_when_cost_within_band():
    result = evaluate_promotion_gate(
        _comparison(cost={"delta_pct": 4.0, "same_gpu": "L4"}), FLOORS
    )
    assert result.promoted


def test_cost_absent_is_not_measured_and_passes():
    result = evaluate_promotion_gate(_comparison(cost=None), FLOORS)
    cost_dec = next(d for d in result.decisions if d.metric == "cost_per_request")
    assert cost_dec.passed
    assert "not measured" in cost_dec.rule


def test_no_regression_mode_blocks_the_real_adapter(tmp_path):
    cfg = {
        "faithfulness": {
            "abs_floor": 0.656,
            "max_regression_vs_base": 0.05,
            "mode": "no_regression",
        },
        "format_validity": {"abs_floor": 0.95},
        "refusal_correctness": {"min_delta_vs_base": 0.0},
        "cost": {"max_regression_pct_vs_base": 10.0},
        "block_reason_required": True,
    }
    p = tmp_path / "floors.json"
    p.write_text(json.dumps(cfg))
    result = evaluate_promotion_gate(_comparison(), load_floors(p))
    assert not result.promoted  # strict band blocks the -0.109 regression despite the format jump


def test_absolute_mode_promotes_on_floor_only(tmp_path):
    cfg = {
        "faithfulness": {"abs_floor": 0.656, "max_regression_vs_base": 0.05, "mode": "absolute"},
        "format_validity": {"abs_floor": 0.95},
        "refusal_correctness": {"min_delta_vs_base": 0.0},
        "cost": {"max_regression_pct_vs_base": 10.0},
        "block_reason_required": True,
    }
    p = tmp_path / "floors.json"
    p.write_text(json.dumps(cfg))
    result = evaluate_promotion_gate(_comparison(), load_floors(p))
    assert result.promoted


def test_blocked_result_always_has_a_reason():
    result = evaluate_promotion_gate(_comparison(faith=(0.787, 0.600)), FLOORS)
    assert not result.promoted
    assert result.blocked_reasons  # block_reason_required contract


def test_emitter_writes_json_and_markdown(tmp_path):
    result = evaluate_promotion_gate(_comparison(), FLOORS)
    write_report(tmp_path, result)
    data = json.loads((tmp_path / "promotion.json").read_text())
    assert data["promoted"] is True
    md = (tmp_path / "promotion-summary.md").read_text()
    assert "PROMOTE" in md and "faithfulness" in md


def test_cli_exit_codes(tmp_path):
    passing = tmp_path / "pass.json"
    passing.write_text(json.dumps(_comparison()))
    blocked = tmp_path / "block.json"
    blocked.write_text(json.dumps(_comparison(faith=(0.787, 0.600))))
    report = tmp_path / "report"

    assert main(["--comparison", str(passing), "--report-dir", str(report)]) == 0
    assert main(["--comparison", str(blocked), "--report-dir", str(report)]) == 1
    # missing file -> block (non-zero)
    assert main(["--comparison", str(tmp_path / "nope.json"), "--report-dir", str(report)]) == 1
