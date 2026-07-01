"""Base-vs-FT comparison report generator (P6 Task 10) — pure, GPU-free, evals-free.

Consumes already-computed per-metric scores for the base and fine-tuned candidates (faithfulness
via RAGAS in the GPU window; format-validity + refusal-correctness via the deterministic evals
scorers) and emits the committed evidence: a `comparison.json` and a `COMPARISON.md` in the same
`{base, ft, delta}` shape as the infra/bench artifact (ADR-0067) — exactly the schema P7's
promotion gate will consume. This module does only arithmetic + formatting, so it is unit-tested
on fixture score dicts with no GPU and no eval/model dependency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas_training.data.manifest import current_git_sha
from atlas_training.stats import CI_METHOD, SIG_TEST, p50_p95, paired_stats

# Canonical metric order + P7 target context (reported, NOT gated in P6).
METRICS = ("faithfulness", "format_validity", "refusal_correctness")
TARGETS = {
    "faithfulness": "FT ≥ base − 0.05 (no-regression band, baseline floor 0.656)",
    "format_validity": "FT ≥ 0.95",
    "refusal_correctness": "FT ≥ base",
}
# How each metric's paired significance is tested (P7 D8/ADR-0082): faithfulness is continuous
# (Wilcoxon signed-rank), format/refusal are binary per-case pass/fail (McNemar exact).
METRIC_KIND = {
    "faithfulness": "continuous",
    "format_validity": "binary",
    "refusal_correctness": "binary",
}


def metric_delta(base: float, ft: float) -> float:
    return round(ft - base, 4)


@dataclass(frozen=True)
class ComparisonResult:
    metrics: dict[str, dict[str, float]]  # name -> {base, ft, delta[, ci95_delta, p_value, ...]}
    model_ids: dict[str, str]             # {base, ft}
    dataset_size: int
    training_cost: dict[str, Any]         # CostRecord.to_dict() (or {} if unavailable)
    git_sha: str
    recorded_at: str
    meta: dict[str, Any] = field(default_factory=dict)
    # NEW in P7: serving cost/latency-per-request base-vs-FT (§2.3, D3/ADR-0077), serialized as the
    # top-level "cost" key the promotion gate reads. Empty until the episodic window measures it.
    cost_per_request: dict[str, Any] = field(default_factory=dict)
    # NEW in P7: report-only statistical rigor labels (D8/ADR-0082). Empty when per-case vectors are
    # not supplied. The per-metric CI/p-value/significance live INSIDE each metrics[m] block.
    ci_method: str = ""
    sig_test: str = ""

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "metrics": self.metrics,
            "model_ids": self.model_ids,
            "dataset_size": self.dataset_size,
            "training_cost": self.training_cost,
            "git_sha": self.git_sha,
            "recorded_at": self.recorded_at,
            "meta": self.meta,
        }
        # Additive, non-breaking: the promotion gate reads only base/ft/delta + cost.delta_pct.
        if self.cost_per_request:
            out["cost"] = self.cost_per_request
        if self.ci_method:
            out["ci_method"] = self.ci_method
        if self.sig_test:
            out["sig_test"] = self.sig_test
        return out

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> ComparisonResult:
        return cls(
            metrics=raw["metrics"],
            model_ids=raw["model_ids"],
            dataset_size=raw["dataset_size"],
            training_cost=raw.get("training_cost", {}),
            git_sha=raw["git_sha"],
            recorded_at=raw["recorded_at"],
            meta=raw.get("meta", {}),
            cost_per_request=raw.get("cost", {}),
            ci_method=raw.get("ci_method", ""),
            sig_test=raw.get("sig_test", ""),
        )


def build_comparison(
    base_scores: dict[str, float],
    ft_scores: dict[str, float],
    *,
    model_ids: dict[str, str],
    dataset_size: int,
    training_cost: dict[str, Any] | None = None,
    git_sha: str | None = None,
    recorded_at: str | None = None,
    meta: dict[str, Any] | None = None,
    cost_per_request: dict[str, Any] | None = None,
    per_case: dict[str, dict[str, list[float]]] | None = None,
    stats_seed: int = 0,
) -> ComparisonResult:
    """Assemble a ComparisonResult, computing per-metric deltas. Requires all canonical metrics.

    ``cost_per_request`` (§2.3, D3): the base-vs-FT serving cost/latency block (from
    ``build_cost_per_request``); serialized as the top-level ``"cost"`` key the gate reads.
    ``per_case`` (D8/ADR-0082): optional ``metric -> {"base": [...], "ft": [...]}`` per-case
    vectors; when supplied, **report-only** paired-bootstrap 95% CIs + a paired significance test
    are embedded inside each ``metrics[m]`` block (alongside base/ft/delta) — the gate ignores them.
    """
    missing = [m for m in METRICS if m not in base_scores or m not in ft_scores]
    if missing:
        raise ValueError(f"missing metric scores for: {missing}")
    metrics: dict[str, dict[str, float]] = {}
    for m in METRICS:
        block: dict[str, Any] = {
            "base": round(float(base_scores[m]), 4),
            "ft": round(float(ft_scores[m]), 4),
            "delta": metric_delta(float(base_scores[m]), float(ft_scores[m])),
        }
        if per_case and m in per_case:
            block.update(
                paired_stats(
                    per_case[m]["base"],
                    per_case[m]["ft"],
                    kind=METRIC_KIND[m],
                    seed=stats_seed,
                )
            )
        metrics[m] = block
    ci_method = CI_METHOD if per_case else ""
    sig_test = SIG_TEST if per_case else ""
    return ComparisonResult(
        metrics=metrics,
        model_ids=model_ids,
        dataset_size=dataset_size,
        training_cost=training_cost or {},
        git_sha=git_sha or current_git_sha(),
        recorded_at=recorded_at or datetime.now(UTC).isoformat(),
        meta=meta or {},
        cost_per_request=cost_per_request or {},
        ci_method=ci_method,
        sig_test=sig_test,
    )


def build_cost_per_request(
    *,
    base_latencies_ms: list[float],
    ft_latencies_ms: list[float],
    base_cost_units_per_req: float,
    ft_cost_units_per_req: float,
    same_gpu: str = "L4",
) -> dict[str, Any]:
    """Assemble the §2.3 cost-per-request block from measured per-request latencies + cost units.

    ``delta_pct`` is the relative cost-per-request regression (ft vs base) the promotion gate's
    cost check reads (D3/ADR-0077); p50/p95 latency are computed for report-only context.
    """
    base_p50, base_p95 = p50_p95(base_latencies_ms)
    ft_p50, ft_p95 = p50_p95(ft_latencies_ms)
    if base_cost_units_per_req > 0:
        delta_pct = round(
            (ft_cost_units_per_req - base_cost_units_per_req) / base_cost_units_per_req * 100.0, 2
        )
    else:
        delta_pct = 0.0
    return {
        "base": {
            "cost_units_per_req": round(float(base_cost_units_per_req), 6),
            "latency_ms_p50": base_p50,
            "latency_ms_p95": base_p95,
        },
        "ft": {
            "cost_units_per_req": round(float(ft_cost_units_per_req), 6),
            "latency_ms_p50": ft_p50,
            "latency_ms_p95": ft_p95,
        },
        "delta_pct": delta_pct,
        "same_gpu": same_gpu,
    }


def _fmt(x: float) -> str:
    return f"{x:+.4f}" if x else "+0.0000"


def comparison_markdown(result: ComparisonResult) -> str:
    """Render COMPARISON.md — bench-style headline + per-metric base/ft/Δ table + provenance."""
    lines: list[str] = []
    lines.append("# Atlas P6 — base vs fine-tuned (QLoRA) comparison\n")
    lines.append(
        f"Candidate **{result.model_ids.get('ft', 'ft')}** vs base "
        f"**{result.model_ids.get('base', 'base')}** over {result.dataset_size} eval cases.\n"
    )

    lines.append("### Metrics (candidate Δ vs base)\n")
    lines.append("| Metric | base | ft | Δ | P7 target (reported, not gated in P6) |")
    lines.append("|---|---|---|---|---|")
    for m in METRICS:
        row = result.metrics[m]
        lines.append(
            f"| {m} | {row['base']:.4f} | {row['ft']:.4f} | {_fmt(row['delta'])} | "
            f"{TARGETS[m]} |"
        )

    # Report-only statistical rigor (D8/ADR-0082): paired-bootstrap 95% CIs + paired significance.
    if any("ci95_delta" in result.metrics[m] for m in METRICS):
        lines.append("\n### Statistical rigor (report-only, not gated — D8/ADR-0082)\n")
        lines.append(
            f"Method: **{result.ci_method}** CIs; significance **{result.sig_test}** "
            f"(Wilcoxon = continuous faithfulness, McNemar = binary format/refusal). "
            f"`significant` ⇔ the 95% CI excludes 0.\n"
        )
        lines.append("| Metric | Δ | 95% CI (Δ) | test | p-value | significant |")
        lines.append("|---|---|---|---|---|---|")
        for m in METRICS:
            row = result.metrics[m]
            if "ci95_delta" not in row:
                continue
            lo, hi = row["ci95_delta"]
            lines.append(
                f"| {m} | {_fmt(row['delta'])} | [{lo:+.4f}, {hi:+.4f}] | {row['test']} | "
                f"{row['p_value']:.4f} | {'yes' if row['significant'] else 'no'} |"
            )

    # Serving cost/latency per request, base vs FT on the same GPU (§2.3, D3/ADR-0077).
    cpr = result.cost_per_request or {}
    if cpr:
        b, f = cpr.get("base", {}), cpr.get("ft", {})
        lines.append(
            f"\n### Serving cost/latency per request (same GPU: {cpr.get('same_gpu', '?')})\n"
        )
        lines.append("| Side | cost_units/req | latency p50 (ms) | latency p95 (ms) |")
        lines.append("|---|---|---|---|")
        lines.append(
            f"| base | {b.get('cost_units_per_req', '?')} | "
            f"{b.get('latency_ms_p50', '?')} | {b.get('latency_ms_p95', '?')} |"
        )
        lines.append(
            f"| ft | {f.get('cost_units_per_req', '?')} | "
            f"{f.get('latency_ms_p50', '?')} | {f.get('latency_ms_p95', '?')} |"
        )
        lines.append(
            f"\n**Cost/req Δ:** {cpr.get('delta_pct', 0.0):+.2f}% vs base "
            f"(promotion band ≤ 10%, ADR-0077; p95 latency report-only)."
        )

    cost = result.training_cost or {}
    if cost:
        lines.append(
            f"\n**Training cost:** {cost.get('cost', '?')} {cost.get('currency', '')} "
            f"({cost.get('wall_seconds', '?')}s wall-clock @ "
            f"{cost.get('rate_per_hour', '?')}/hr)."
        )

    lines.append("\n### Provenance\n")
    lines.append(f"- dataset size: {result.dataset_size}")
    lines.append(f"- base model: {result.model_ids.get('base', '?')}")
    lines.append(f"- ft adapter: {result.model_ids.get('ft', '?')}")
    lines.append(f"- git: {result.git_sha}")
    lines.append(f"- recorded: {result.recorded_at}")
    lines.append("")
    return "\n".join(lines)


def write_comparison(result: ComparisonResult, out_dir: str | Path) -> tuple[Path, Path]:
    """Write comparison.json + COMPARISON.md into `out_dir`. Returns the two paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out / "comparison.json", out / "COMPARISON.md"
    result.save(json_path)
    md_path.write_text(comparison_markdown(result), encoding="utf-8")
    return json_path, md_path
