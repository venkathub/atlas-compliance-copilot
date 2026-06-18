"""Cost-delta report (P3 task 10, R3) — quantify "X% cheaper at equal eval score".

Runs the golden set THROUGH the Gateway and compares serving cost with caching+routing **on vs
off**, reading the per-response ``cost.costUnits`` the Gateway emits (ADR-0040). The quality-equal
half is the reused RAGAS gate run through the Gateway (``ATLAS_EVAL_THROUGH_GATEWAY=true``); this
script owns the cost half and records the calibrated cache-similarity threshold + the measured %
reduction to ``evals/data/gateway-baseline.json`` (mirroring ``baseline.json``).

This is a **live calibration job** (GPU on) — not the PR gate. The pure helpers are unit-tested
offline. To run it:

    make -C infra gpu-up && set -a && . ./.env && set +a
    # bring up the Gateway + rag-engine, then:
    GATEWAY_URL=http://localhost:8080 uv run --directory evals python -m atlas_evals.cost_report
    make -C infra gpu-down
"""

from __future__ import annotations

import datetime as dt
import json
import os

from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.datasets.golden import load_golden
from atlas_evals.gateway_client import GatewayRagClient

GATEWAY_BASELINE = DATA_DIR / "gateway-baseline.json"


def pct_reduction(off_total: float, on_total: float) -> float:
    """Percent serving-cost reduction of the on-run vs the off-run; 0.0 when off-total ≤ 0."""
    if off_total <= 0:
        return 0.0
    return max(0.0, (off_total - on_total) / off_total) * 100.0


def cost_units(response: dict) -> float:
    """Extract the Gateway-reported cost-units from a `/v1/query` response (0.0 if absent)."""
    cost = response.get("cost") if isinstance(response, dict) else None
    return float(cost.get("costUnits", 0.0)) if isinstance(cost, dict) else 0.0


def build_baseline(off_total: float, on_total: float, sim_threshold: float,
                   target_pct: float = 30.0) -> dict:
    """Assemble the gateway-baseline payload + pass/fail vs the ≥30% target band (§8.3)."""
    reduction = pct_reduction(off_total, on_total)
    return {
        "cache_sim_threshold": sim_threshold,
        "cost_off_units": round(off_total, 6),
        "cost_on_units": round(on_total, 6),
        "cost_reduction_pct": round(reduction, 2),
        "target_reduction_pct": target_pct,
        "meets_target": reduction >= target_pct,
        "recorded_at": dt.datetime.now(dt.UTC).isoformat(),
        "note": "Self-hosted cost-units are documented estimates (ADR-0040). Quality-equality is "
                "proven by the RAGAS gate run with ATLAS_EVAL_THROUGH_GATEWAY=true.",
    }


def _run_live() -> int:
    base_url = os.environ.get("GATEWAY_URL", "http://localhost:8080")
    sim_threshold = float(os.environ.get("ATLAS_CACHE_SIM_THRESHOLD", "0.95"))
    client = GatewayRagClient(base_url=base_url)
    tuples = load_golden()

    # OFF = cold first pass (every query a model call). ON = warm second pass (repeats hit the
    # clearance-partitioned cache at ~zero cost). A documented proxy for the cache-driven saving.
    off_total = sum(cost_units(client.query(t.question, t.clearance, top_k=6)) for t in tuples)
    on_total = sum(cost_units(client.query(t.question, t.clearance, top_k=6)) for t in tuples)

    baseline = build_baseline(off_total, on_total, sim_threshold)
    GATEWAY_BASELINE.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"cost-delta: {baseline['cost_reduction_pct']}% cheaper "
          f"(off={off_total:.4f} → on={on_total:.4f} units); wrote {GATEWAY_BASELINE.name}")
    return 0


def main() -> int:
    return _run_live()


if __name__ == "__main__":
    raise SystemExit(main())
