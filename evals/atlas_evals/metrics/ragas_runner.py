"""RAGAS runner orchestration (RAGAS-free, so it is unit-testable with a fake scorer).

The runner joins golden tuples with their `/v1/query` responses, delegates RAGAS metric computation
to an injected `Scorer` (the concrete `RagasScorer` runs the real metrics against the judge; tests
use a fake), and adds the deterministic citation-correctness signal. The *gating* decision
(which metrics gate, vs report-only) lives in the gate (Task 8), not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Protocol

from atlas_evals.datasets.golden import GoldenTuple
from atlas_evals.metrics.citation import citation_resolution_rate
from atlas_evals.metrics.samples import EvalSample, build_samples


class Scorer(Protocol):
    """Computes RAGAS metric means over a set of samples → {metric_name: score}."""

    def score(self, samples: list[EvalSample]) -> dict[str, float]:
        ...


@dataclass
class MetricReport:
    scores: dict[str, float] = field(default_factory=dict)
    n_samples: int = 0


class RagasRunner:
    def __init__(self, scorer: Scorer) -> None:
        self.scorer = scorer

    def run(self, tuples: list[GoldenTuple], responses: dict[str, dict]) -> MetricReport:
        samples = build_samples(tuples, responses)
        scores = dict(self.scorer.score(samples))
        # Deterministic, judge-free citation-correctness (report-only) — computed here, not by the
        # judge, so it is stable and cheap.
        scores["citation_correctness"] = fmean(
            citation_resolution_rate(s.answer, len(s.contexts)) for s in samples
        ) if samples else 1.0
        return MetricReport(scores=scores, n_samples=len(samples))
