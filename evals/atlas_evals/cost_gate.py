"""Cost-regression merge/deploy gate (P6 Task 5, ADR-0064).

Pairs with the RAGAS + adversarial gate (`atlas_evals.gate`) so CI blocks a merge/deploy on EITHER a
**quality** regression (hallucination up via the faithfulness floor + 100%-pass adversarial gate) OR
a **cost** regression — the two halves of "don't ship a worse answer, and don't ship a pricier one."
Offline + GPU-free: it validates the committed cost evidence (`gateway-baseline.json`, produced live
by `atlas_evals.cost_report`, RUNBOOK §7.4) against its target band.

`evaluate_cost_gate` is a pure function (unit-tested); the CLI loads the baseline and exits non-zero
on any breach so it blocks the pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from atlas_evals.datasets.corpus import DATA_DIR

GATEWAY_BASELINE = DATA_DIR / "gateway-baseline.json"
_EPS = 1e-9


@dataclass
class CostGateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def evaluate_cost_gate(cost: dict) -> CostGateResult:
    """Pure decision: the recorded cost reduction must meet its target and not absolutely regress.

    Gates (any breach fails):
      * ``cost_reduction_pct`` >= ``target_reduction_pct`` (the optimization still holds);
      * ``meets_target`` is not explicitly false;
      * (optional, forward-compatible) ``cost_on_units`` <= ``max_cost_on_units`` if that ceiling
        field is present — catches an absolute cost bump even when the reduction % holds.
    """
    failures: list[str] = []
    reduction = cost.get("cost_reduction_pct")
    target = cost.get("target_reduction_pct")
    meets = cost.get("meets_target")
    on_units = cost.get("cost_on_units")
    ceiling = cost.get("max_cost_on_units")

    if reduction is None or target is None:
        failures.append(
            "cost baseline missing 'cost_reduction_pct' / 'target_reduction_pct' "
            "(re-run atlas_evals.cost_report — RUNBOOK §7.4)"
        )
    elif reduction + _EPS < target:
        failures.append(
            f"cost reduction {reduction:.1f}% < target {target:.1f}% — cost regressed below band"
        )

    if meets is False:
        failures.append("gateway-baseline 'meets_target' is false")

    if ceiling is not None and on_units is not None and on_units > ceiling + _EPS:
        failures.append(
            f"cost_on_units {on_units:.3f} > ceiling {ceiling:.3f} — absolute cost regression"
        )

    return CostGateResult(
        passed=not failures,
        failures=failures,
        summary={
            "cost_reduction_pct": reduction,
            "target_reduction_pct": target,
            "cost_on_units": on_units,
            "max_cost_on_units": ceiling,
        },
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="atlas_evals.cost_gate", description="Atlas cost-regression gate"
    )
    ap.add_argument(
        "--baseline", default=str(GATEWAY_BASELINE), help="path to gateway-baseline.json"
    )
    args = ap.parse_args(argv)

    path = Path(args.baseline)
    if not path.exists():
        print(f"COST GATE: FAIL — baseline not found: {path}")
        return 1

    cost = json.loads(path.read_text())
    result = evaluate_cost_gate(cost)
    s = result.summary
    print("COST GATE:", "PASS" if result.passed else "FAIL")
    print(
        f"  reduction={s.get('cost_reduction_pct')}% target={s.get('target_reduction_pct')}% "
        f"on_units={s.get('cost_on_units')} ceiling={s.get('max_cost_on_units')}"
    )
    for f in result.failures:
        print("  -", f)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
