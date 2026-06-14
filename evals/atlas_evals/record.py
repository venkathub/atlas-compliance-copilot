"""Live cassette recorder (RECORD mode) — run during the GPU calibration session (Task 8/9).

Resumes nothing itself (the GPU helper wraps it): assumes ``OLLAMA_BASE_URL`` is set and rag-engine
is up + ingested. For each golden tuple it records the `/v1/query` response, then runs RAGAS against
the live judge and records per-sample scores. The committed cassettes then drive the offline gate.

    uv run --directory evals --group ragas python -m atlas_evals.record
"""

from __future__ import annotations

import os

from atlas_evals.cassettes import CassetteStore, Mode
from atlas_evals.client import AtlasRagClient, CassettingClient
from atlas_evals.datasets.adversarial import load_adversarial
from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.datasets.golden import load_golden
from atlas_evals.metrics.ragas_runner import RagasRunner
from atlas_evals.metrics.ragas_scorer import RagasScorer

RAG_CASSETTES = DATA_DIR / "cassettes" / "rag"
JUDGE_CASSETTES = DATA_DIR / "cassettes" / "judge"


def _fingerprint() -> str:
    """Bust cassettes when the RAG/embed model tags change."""
    return "|".join([
        os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b-instruct"),
        os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    ])


def main() -> int:
    base_url = os.environ["RAG_ENGINE_URL"] if "RAG_ENGINE_URL" in os.environ else "http://localhost:8081"
    judge_model = os.environ.get("ATLAS_EVAL_JUDGE_MODEL", "llama3.1:8b")
    judge_base = os.environ.get("ATLAS_EVAL_JUDGE_BASE_URL") or os.environ["OLLAMA_BASE_URL"]
    embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    # FILL (default) is resumable: existing cassettes are kept, only missing ones are recorded.
    mode = Mode(os.environ.get("ATLAS_CASSETTE_MODE", "fill"))

    tuples = load_golden()
    rag = CassettingClient(
        AtlasRagClient(base_url=base_url),
        CassetteStore(RAG_CASSETTES, mode),
        fingerprint=_fingerprint(),
    )
    responses = {
        t.id: rag.query(t.question, t.clearance, top_k=6, include_contexts=True) for t in tuples
    }
    print(f"recorded {len(responses)} /v1/query cassettes -> {RAG_CASSETTES}")

    # Adversarial queries share the same RAG cassette store (each run at the case's clearance).
    adv_cases = load_adversarial()
    for case in adv_cases:
        rag.query(case.query, case.clearance, top_k=6, include_contexts=True)
    print(f"recorded {len(adv_cases)} adversarial /v1/query cassettes")

    scorer = RagasScorer(
        store=CassetteStore(JUDGE_CASSETTES, mode),
        judge_model=judge_model,
        embed_model=embed_model,
        base_url=judge_base,
        fingerprint=_ragas_fingerprint(),
    )
    report = RagasRunner(scorer).run(tuples, responses)
    print(f"recorded judge cassettes -> {JUDGE_CASSETTES}")
    print("metric means:", {k: round(v, 3) for k, v in report.scores.items()})
    return 0


def _ragas_fingerprint() -> str:
    try:
        import ragas

        return f"ragas:{ragas.__version__}"
    except Exception:
        return "ragas:unknown"


if __name__ == "__main__":
    raise SystemExit(main())
