from atlas_evals.cost_report import build_baseline, cost_units, pct_reduction


def test_pct_reduction_basic():
    assert pct_reduction(10.0, 4.0) == 60.0
    assert pct_reduction(10.0, 10.0) == 0.0
    assert pct_reduction(0.0, 0.0) == 0.0  # no off-cost → no claim
    assert pct_reduction(10.0, 12.0) == 0.0  # never report a negative reduction


def test_cost_units_extraction():
    assert cost_units({"cost": {"costUnits": 0.0041}}) == 0.0041
    assert cost_units({"answer": "x"}) == 0.0  # no cost section
    assert cost_units({"cost": {}}) == 0.0
    assert cost_units("not-a-dict") == 0.0


def test_build_baseline_meets_target():
    # 1.0 off → 0.5 on = 50% reduction ≥ 30% target.
    b = build_baseline(off_total=1.0, on_total=0.5, sim_threshold=0.95)
    assert b["cost_reduction_pct"] == 50.0
    assert b["meets_target"] is True
    assert b["cache_sim_threshold"] == 0.95
    assert b["target_reduction_pct"] == 30.0
    assert "recorded_at" in b


def test_build_baseline_below_target():
    # 1.0 off → 0.8 on = 20% reduction < 30% target.
    b = build_baseline(off_total=1.0, on_total=0.8, sim_threshold=0.95)
    assert b["cost_reduction_pct"] == 20.0
    assert b["meets_target"] is False
