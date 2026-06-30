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

# Canonical metric order + P7 target context (reported, NOT gated in P6).
METRICS = ("faithfulness", "format_validity", "refusal_correctness")
TARGETS = {
    "faithfulness": "FT ≥ base − 0.05 (no-regression band, baseline floor 0.656)",
    "format_validity": "FT ≥ 0.95",
    "refusal_correctness": "FT ≥ base",
}


def metric_delta(base: float, ft: float) -> float:
    return round(ft - base, 4)


@dataclass(frozen=True)
class ComparisonResult:
    metrics: dict[str, dict[str, float]]  # name -> {base, ft, delta}
    model_ids: dict[str, str]             # {base, ft}
    dataset_size: int
    training_cost: dict[str, Any]         # CostRecord.to_dict() (or {} if unavailable)
    git_sha: str
    recorded_at: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics,
            "model_ids": self.model_ids,
            "dataset_size": self.dataset_size,
            "training_cost": self.training_cost,
            "git_sha": self.git_sha,
            "recorded_at": self.recorded_at,
            "meta": self.meta,
        }

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
) -> ComparisonResult:
    """Assemble a ComparisonResult, computing per-metric deltas. Requires all canonical metrics."""
    missing = [m for m in METRICS if m not in base_scores or m not in ft_scores]
    if missing:
        raise ValueError(f"missing metric scores for: {missing}")
    metrics = {
        m: {
            "base": round(float(base_scores[m]), 4),
            "ft": round(float(ft_scores[m]), 4),
            "delta": metric_delta(float(base_scores[m]), float(ft_scores[m])),
        }
        for m in METRICS
    }
    return ComparisonResult(
        metrics=metrics,
        model_ids=model_ids,
        dataset_size=dataset_size,
        training_cost=training_cost or {},
        git_sha=git_sha or current_git_sha(),
        recorded_at=recorded_at or datetime.now(UTC).isoformat(),
        meta=meta or {},
    )


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
