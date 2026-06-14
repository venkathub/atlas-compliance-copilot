"""Baseline / threshold anchor (ADR-0024) — the no-regression contract for the gate.

`baseline.json` records the calibrated floors + last-known-good scores + the pinned judge/model/
fingerprint metadata, so a metric move can only mean *the RAG changed* (never the judge or the
cassette key scheme). Floors are absolute; `max_regression` blocks a silent slide while above floor.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from atlas_evals.datasets.corpus import DATA_DIR

DEFAULT_PATH = DATA_DIR / "baseline.json"

# D-P2-4: gate these three (floor + no-regression); the rest are report-only (phase-in).
GATING_METRICS = ("faithfulness", "answer_relevancy", "context_recall")
REPORT_ONLY_METRICS = (
    "context_precision",
    "context_entity_recall",
    "noise_sensitivity",
    "citation_correctness",
)
# Per-metric no-regression band + the margin floors sit below the first calibrated run.
MAX_REGRESSION = {"faithfulness": 0.05, "answer_relevancy": 0.05, "context_recall": 0.07}
FLOOR_MARGIN = {"faithfulness": 0.05, "answer_relevancy": 0.05, "context_recall": 0.07}


@dataclass
class MetricThreshold:
    baseline: float | None = None
    floor: float | None = None
    max_regression: float | None = None
    report_only: bool = False


@dataclass
class Baseline:
    metrics: dict[str, MetricThreshold] = field(default_factory=dict)
    adversarial_must_pass_rate: float = 1.0
    judge_model: str = ""
    judge_temperature: float = 0.0
    rag_model: str = ""
    embed_model: str = ""
    rag_fingerprint: str = ""
    ragas_fingerprint: str = ""
    semconv_optin: str = ""
    recorded_at: str = ""
    git_sha: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["metrics"] = {k: asdict(v) for k, v in self.metrics.items()}
        return d


def load_baseline(path: Path = DEFAULT_PATH) -> Baseline:
    obj = json.loads(path.read_text())
    metrics = {k: MetricThreshold(**v) for k, v in obj.get("metrics", {}).items()}
    obj = {**obj, "metrics": metrics}
    return Baseline(**obj)


def save_baseline(baseline: Baseline, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline.to_json(), indent=2) + "\n")


def calibrate(
    scores: dict[str, float],
    *,
    judge_model: str,
    rag_model: str,
    embed_model: str,
    rag_fingerprint: str,
    ragas_fingerprint: str,
    semconv_optin: str = "",
    git_sha: str = "",
) -> Baseline:
    """Build a baseline from a green calibration run: floor = recorded − margin (clamped ≥ 0)."""
    metrics: dict[str, MetricThreshold] = {}
    for name, value in scores.items():
        if name in GATING_METRICS:
            margin = FLOOR_MARGIN.get(name, 0.05)
            metrics[name] = MetricThreshold(
                baseline=round(value, 3),
                floor=round(max(0.0, value - margin), 3),
                max_regression=MAX_REGRESSION.get(name, 0.05),
                report_only=False,
            )
        else:
            metrics[name] = MetricThreshold(baseline=round(value, 3), report_only=True)
    return Baseline(
        metrics=metrics,
        adversarial_must_pass_rate=1.0,
        judge_model=judge_model,
        judge_temperature=0.0,
        rag_model=rag_model,
        embed_model=embed_model,
        rag_fingerprint=rag_fingerprint,
        ragas_fingerprint=ragas_fingerprint,
        semconv_optin=semconv_optin,
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_sha=git_sha,
    )
