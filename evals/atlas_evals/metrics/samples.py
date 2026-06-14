"""Map (golden tuple + /v1/query response) → flat eval samples (RAGAS-free).

Keeping this conversion dependency-free means the harness's data plumbing is unit-tested without
installing RAGAS; the concrete scorer converts these into RAGAS `SingleTurnSample`s.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from atlas_evals.datasets.golden import GoldenTuple


@dataclass(frozen=True)
class EvalSample:
    """One (question, answer, retrieved-contexts, ground-truth) record for scoring."""

    id: str
    question: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    ground_truth: str = ""


def build_samples(tuples: list[GoldenTuple], responses: dict[str, dict]) -> list[EvalSample]:
    """Join golden tuples with their `/v1/query` responses (keyed by tuple id).

    ``contexts`` come from the response's ``contexts[]`` (the eval-context opt-in, ADR-0023) — the
    full RBAC-filtered chunk text the model saw, which RAGAS faithfulness/precision/recall require.
    """
    samples: list[EvalSample] = []
    for t in tuples:
        if t.id not in responses:
            raise KeyError(f"no /v1/query response for golden tuple '{t.id}'")
        resp = responses[t.id]
        contexts = [c.get("text", "") for c in (resp.get("contexts") or [])]
        samples.append(EvalSample(
            id=t.id,
            question=t.question,
            answer=resp.get("answer", ""),
            contexts=contexts,
            ground_truth=t.ground_truth,
        ))
    return samples
