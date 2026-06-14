"""A/B comparison of two cassette sets (RRF/plainto baseline vs reranker/websearch variant).

The eval-gated decision for ADR-0027 / D-P2-7: run the harness against each cassette root in REPLAY
and print the per-metric delta. The numbers (not opinion) decide whether the reranker + sparse fix
are adopted or re-deferred. Run in the calibration lane (after recording the variant live):

    ATLAS_AB_VARIANT=/tmp/cassettes-variant uv run --group ragas python -m atlas_evals.ab
"""

from __future__ import annotations

import os
from pathlib import Path

from atlas_evals.cassettes import CassetteStore, Mode
from atlas_evals.client import AtlasRagClient, CassettingClient
from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.datasets.golden import load_golden
from atlas_evals.fingerprint import rag_fingerprint, ragas_fingerprint
from atlas_evals.metrics.ragas_runner import RagasRunner
from atlas_evals.metrics.ragas_scorer import RagasScorer

REPORT = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def scores_for(root: Path) -> dict[str, float]:
    tuples = load_golden()
    rag = CassettingClient(
        AtlasRagClient(base_url="http://replay.invalid"),
        CassetteStore(root / "rag", Mode.REPLAY),
        fingerprint=rag_fingerprint(),
    )
    responses = {
        t.id: rag.query(t.question, t.clearance, top_k=6, include_contexts=True) for t in tuples
    }
    scorer = RagasScorer(
        store=CassetteStore(root / "judge", Mode.REPLAY),
        judge_model=os.environ.get("ATLAS_EVAL_JUDGE_MODEL", "llama3.1:8b"),
        embed_model=os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url="",
        fingerprint=ragas_fingerprint(),
    )
    return RagasRunner(scorer).run(tuples, responses).scores


def main() -> int:
    baseline_root = Path(os.environ.get("ATLAS_AB_BASELINE", str(DATA_DIR / "cassettes")))
    variant_root = Path(os.environ["ATLAS_AB_VARIANT"])
    base = scores_for(baseline_root)
    var = scores_for(variant_root)

    print(f"{'metric':<22} {'baseline':>10} {'variant':>10} {'delta':>10}")
    print("-" * 54)
    improved = 0
    for m in REPORT:
        b = base.get(m)
        v = var.get(m)
        if b is None or v is None:
            print(f"{m:<22} {str(b):>10} {str(v):>10} {'n/a':>10}")
            continue
        delta = v - b
        improved += 1 if delta > 0 else 0
        print(f"{m:<22} {b:>10.3f} {v:>10.3f} {delta:>+10.3f}")
    print("-" * 54)
    print(f"metrics improved: {improved}/{len(REPORT)} — keep only on a clear, broad lift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
