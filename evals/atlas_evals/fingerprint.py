"""Stable cassette fingerprints shared by the recorder and the gate.

The fingerprint must be identical at RECORD time (judge/ragas installed) and at REPLAY time (CI,
where neither is installed) or every cassette would miss. So the gate reads the recorded
fingerprints back from `baseline.json` rather than recomputing them; these helpers are only used at
RECORD/recalibrate time (where the live env is available).
"""

from __future__ import annotations

import os


def rag_fingerprint() -> str:
    """Bust RAG cassettes when the RAG/embed model tags change."""
    return "|".join([
        os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b-instruct"),
        os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    ])


def ragas_fingerprint() -> str:
    """Bust judge cassettes when the RAGAS version changes (judge model is keyed separately)."""
    try:
        import ragas

        return f"ragas:{ragas.__version__}"
    except Exception:
        return "ragas:unknown"
