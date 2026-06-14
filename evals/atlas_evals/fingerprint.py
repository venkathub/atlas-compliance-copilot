"""Stable cassette fingerprints shared by the recorder and the gate.

Two fingerprints key the cassettes:

* **RAG fingerprint** — RAG/embed model tags **plus a hash of the rag-engine behaviour-defining
  source** (prompts, guardrail, retrieval/fusion/rerank). The gate **recomputes this live** from the
  checked-out code, so a PR that changes how answers/contexts are produced changes the key → the
  committed cassette no longer matches → a **loud miss** that demands a re-record (the spec's
  "cassette key = hash(prompt + model + inputs)" intent). Without this, the gate would replay stale
  answers and miss a RAG regression.
* **RAGAS fingerprint** — the judge/RAGAS version. CI replay has no RAGAS installed, so the gate
  reads it back from ``baseline.json`` (can't recompute it); a change requires a live recalibration.
"""

from __future__ import annotations

import hashlib
import os

from atlas_evals.datasets.corpus import REPO_ROOT

# rag-engine source whose content determines the answer / retrieved contexts / citations. A change
# to any of these alters behaviour, so it must bust the RAG cassettes (conservative: re-record).
BEHAVIOUR_FILES = (
    "rag-engine/src/main/java/com/atlas/ragengine/qa/QueryService.java",
    "rag-engine/src/main/java/com/atlas/ragengine/qa/CitationExtractor.java",
    "rag-engine/src/main/java/com/atlas/ragengine/guardrail/InjectionGuardrail.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/HybridDocumentRetriever.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/DenseRetriever.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/SparseRetriever.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/ReciprocalRankFusion.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/RrfPassThroughReranker.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/LlmReranker.java",
    "rag-engine/src/main/java/com/atlas/ragengine/retrieval/RetrievalProperties.java",
)


def rag_behaviour_hash() -> str:
    """8-char hash of the rag-engine behaviour-defining source (stable across record + gate)."""
    h = hashlib.sha256()
    for rel in BEHAVIOUR_FILES:
        path = REPO_ROOT / rel
        h.update(rel.encode("utf-8"))
        h.update(path.read_bytes() if path.exists() else b"<missing>")
    return h.hexdigest()[:8]


def rag_fingerprint() -> str:
    """Bust RAG cassettes when the RAG/embed model **or the rag-engine behaviour code** changes."""
    return "|".join([
        os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b-instruct"),
        os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        "rag:" + rag_behaviour_hash(),
    ])


def ragas_fingerprint() -> str:
    """Bust judge cassettes when the RAGAS version changes (judge model is keyed separately)."""
    try:
        import ragas

        return f"ragas:{ragas.__version__}"
    except Exception:
        return "ragas:unknown"
