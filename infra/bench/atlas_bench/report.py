"""Serialize benchmark runs to JSON and render a Markdown comparison table.

A "run" = one backend (ollama|vllm) + model + GPU + list[BenchPoint] across concurrency
levels. ``compare_markdown`` aligns two or more runs by concurrency so the Ollama↔vLLM
crossover (where continuous batching pulls ahead) is visible at a glance.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from atlas_bench.metrics import BenchPoint, cost_per_million_tokens


@dataclass
class BenchRun:
    backend: str  # "ollama" | "vllm"
    model: str
    gpu: str
    gpu_cost_per_hour: float
    points: list[BenchPoint]
    token_accounting: str = "server-reported"  # or "proxy" when usage was unavailable
    notes: str = ""
    meta: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "backend": self.backend,
            "model": self.model,
            "gpu": self.gpu,
            "gpu_cost_per_hour": self.gpu_cost_per_hour,
            "token_accounting": self.token_accounting,
            "notes": self.notes,
            "meta": self.meta,
            "points": [p.as_dict() for p in self.points],
        }

    def write_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2)
            f.write("\n")


def peak_throughput(run: BenchRun) -> BenchPoint | None:
    """The concurrency level at which this backend hit its highest tok/s."""
    return max(run.points, key=lambda p: p.output_tokens_per_s, default=None)


def compare_markdown(runs: Sequence[BenchRun]) -> str:
    """Render a per-concurrency comparison table plus a peak-throughput/cost summary."""
    if not runs:
        return "_(no runs)_\n"

    levels = sorted({p.concurrency for run in runs for p in run.points})
    by_level = {
        run.backend: {p.concurrency: p for p in run.points} for run in runs
    }

    lines: list[str] = []
    lines.append("### Throughput — output tokens/sec by concurrency\n")
    header = "| Concurrency | " + " | ".join(r.backend for r in runs) + " |"
    sep = "|" + "---|" * (len(runs) + 1)
    lines.append(header)
    lines.append(sep)
    for lvl in levels:
        cells = []
        for run in runs:
            p = by_level[run.backend].get(lvl)
            cells.append(f"{p.output_tokens_per_s:.1f}" if p else "—")
        lines.append(f"| {lvl} | " + " | ".join(cells) + " |")

    lines.append("\n### Latency p99 (end-to-end, ms) by concurrency\n")
    lines.append(header)
    lines.append(sep)
    for lvl in levels:
        cells = []
        for run in runs:
            p = by_level[run.backend].get(lvl)
            cells.append(f"{p.e2e_p99_ms:.0f}" if p else "—")
        lines.append(f"| {lvl} | " + " | ".join(cells) + " |")

    lines.append("\n### Peak throughput & measured cost\n")
    lines.append("| Backend | Model | Peak tok/s | @concurrency | Cost / 1M tok | Token acct |")
    lines.append("|---|---|---|---|---|---|")
    for run in runs:
        peak = peak_throughput(run)
        if peak is None:
            continue
        cost = cost_per_million_tokens(run.gpu_cost_per_hour, peak.output_tokens_per_s)
        lines.append(
            f"| {run.backend} | {run.model} | {peak.output_tokens_per_s:.1f} | "
            f"{peak.concurrency} | {cost:.4f} | {run.token_accounting} |"
        )

    # Honest headline ratio (only if exactly two runs).
    if len(runs) == 2:
        a, b = (peak_throughput(runs[0]), peak_throughput(runs[1]))
        if a and b and a.output_tokens_per_s > 0:
            ratio = b.output_tokens_per_s / a.output_tokens_per_s
            lines.append(
                f"\n> **Peak throughput ratio ({runs[1].backend} / {runs[0].backend}): "
                f"{ratio:.2f}×** (same GPU, same model family). "
                f"See notes for quantization caveats."
            )
    lines.append("")
    return "\n".join(lines)
