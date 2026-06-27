#!/usr/bin/env python3
"""Refresh the committed eval/cost summary artifacts the UI Admin page reads (P5 Task 6).

The P5 spec's "committed gate artifact" did not previously exist as a tracked file:
``evals/report/metrics.json`` is gitignored (CI-only) and the agent gate prints JSON to
stdout only. This script snapshots the REAL gate outputs into two small, committed,
camelCase JSON files served by the UI as static assets:

  ui/public/eval-summary.json   - RAG gate (RAGAS + adversarial) + agent gate scores
  ui/public/cost-summary.json   - the P3 cost-reduction headline (gateway-baseline.json)

It changes NO eval logic or thresholds — it only reads/normalizes existing results:
  - RAG:   evals/report/metrics.json   (run `python -m atlas_evals.gate` first to refresh)
  - agent: `python -m app.eval.agent_gate` stdout (offline, deterministic)
  - cost:  evals/data/gateway-baseline.json

Usage (from repo root):
    uv run --directory agents python -m app.eval.agent_gate > /tmp/agent.json 2>/dev/null
    python evals/scripts/refresh_eval_summary.py            # auto-runs the agent gate

Re-run whenever the gates are re-recorded; commit the refreshed JSON files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAG_METRICS = REPO_ROOT / "evals" / "report" / "metrics.json"
GATEWAY_BASELINE = REPO_ROOT / "evals" / "data" / "gateway-baseline.json"
AGENTS_DIR = REPO_ROOT / "agents"
OUT_EVAL = REPO_ROOT / "ui" / "public" / "eval-summary.json"
OUT_COST = REPO_ROOT / "ui" / "public" / "cost-summary.json"


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def load_rag() -> dict:
    if not RAG_METRICS.exists():
        raise SystemExit(
            f"missing {RAG_METRICS} — run the RAG gate "
            "(`uv run --directory evals python -m atlas_evals.gate`) first"
        )
    data = json.loads(RAG_METRICS.read_text())
    scores = data.get("scores", {})
    return {
        "passed": bool(data.get("gate", {}).get("passed", False)),
        "nSamples": data.get("n_samples"),
        "scores": {
            "faithfulness": _round(scores.get("faithfulness")),
            "answerRelevancy": _round(scores.get("answer_relevancy")),
            "contextPrecision": _round(scores.get("context_precision")),
            "contextRecall": _round(scores.get("context_recall")),
            "citationCorrectness": _round(scores.get("citation_correctness")),
        },
        "adversarialPassRate": _round(data.get("adversarial", {}).get("pass_rate")),
        "recordedAt": data.get("recorded_at"),
        "judgeModel": data.get("judge_model"),
    }


def run_agent_gate() -> dict:
    """Run the deterministic, offline agent gate and parse its leading JSON object."""
    proc = subprocess.run(
        ["uv", "run", "--directory", str(AGENTS_DIR), "python", "-m", "app.eval.agent_gate"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout
    start = out.find("{")
    if start == -1:
        raise SystemExit(
            f"agent gate produced no JSON (exit {proc.returncode})\n{proc.stderr[:500]}"
        )
    # Parse the first balanced JSON object.
    depth = 0
    for i in range(start, len(out)):
        if out[i] == "{":
            depth += 1
        elif out[i] == "}":
            depth -= 1
            if depth == 0:
                obj = json.loads(out[start : i + 1])
                break
    else:
        raise SystemExit("could not parse agent gate JSON")
    return {
        "passed": "AGENT GATE: PASS" in out,
        "scenarios": obj.get("scenarios"),
        "taskSuccessRate": _round(obj.get("task_success_rate")),
        "toolSelectionRate": _round(obj.get("tool_selection_rate")),
        "argumentCorrectnessRate": _round(obj.get("argument_correctness_rate")),
        "planAdherenceRate": _round(obj.get("plan_adherence_rate")),
        "stepEfficiencyRate": _round(obj.get("step_efficiency_rate")),
        "hitlRespected": bool(obj.get("hitl_respected")),
        "authorizationRespected": bool(obj.get("authorization_respected")),
        "unapprovedWrites": obj.get("unapproved_writes"),
        "unauthorizedWrites": obj.get("unauthorized_writes"),
    }


def load_cost() -> dict:
    data = json.loads(GATEWAY_BASELINE.read_text())
    return {
        "costReductionPct": _round(data.get("cost_reduction_pct"), 1),
        "targetReductionPct": _round(data.get("target_reduction_pct"), 1),
        "meetsTarget": bool(data.get("meets_target")),
        "costOffUnits": _round(data.get("cost_off_units")),
        "costOnUnits": _round(data.get("cost_on_units")),
        "cacheSimThreshold": _round(data.get("cache_sim_threshold")),
        "recordedAt": data.get("recorded_at"),
    }


def git_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() or "unknown"


def main() -> int:
    generated_at = datetime.now(UTC).isoformat()
    sha = git_sha()
    eval_summary = {
        "generatedAt": generated_at,
        "gitSha": sha,
        "rag": load_rag(),
        "agent": run_agent_gate(),
    }
    cost_summary = {"generatedAt": generated_at, "gitSha": sha, **load_cost()}

    OUT_EVAL.write_text(json.dumps(eval_summary, indent=2) + "\n")
    OUT_COST.write_text(json.dumps(cost_summary, indent=2) + "\n")
    print(f"wrote {OUT_EVAL.relative_to(REPO_ROOT)} and {OUT_COST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
