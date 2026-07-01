"""Proof-it-bites contract: the committed fixtures promote/block as designed (P7 Task 3).

Binds the two committed fixtures (``evals/data/promotion/{pass,blocked}/comparison.json``) to the
gate so the pass/block guarantee the CI matrix (Task 4) asserts is also locked into the test suite
and cannot silently rot if the gate policy or floors change.
"""

import json

from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.promotion_floors import load_floors
from atlas_evals.promotion_gate import evaluate_promotion_gate

FLOORS = load_floors()
PASS_FIXTURE = DATA_DIR / "promotion" / "pass" / "comparison.json"
BLOCKED_FIXTURE = DATA_DIR / "promotion" / "blocked" / "comparison.json"


def _load(path):
    return json.loads(path.read_text())


def test_pass_fixture_promotes():
    result = evaluate_promotion_gate(_load(PASS_FIXTURE), FLOORS)
    assert result.promoted, result.blocked_reasons
    assert result.blocked_reasons == []


def test_pass_fixture_matches_real_committed_result():
    # The pass fixture must stay a faithful copy of the real P6 comparison it stands in for.
    real = _load(DATA_DIR.parent.parent / "training" / "results" / "comparison.json")
    assert _load(PASS_FIXTURE)["metrics"] == real["metrics"]


def test_blocked_fixture_is_blocked_below_floor():
    result = evaluate_promotion_gate(_load(BLOCKED_FIXTURE), FLOORS)
    assert not result.promoted
    assert any("below floor" in r for r in result.blocked_reasons)
