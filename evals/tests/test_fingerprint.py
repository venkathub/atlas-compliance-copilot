from atlas_evals.fingerprint import (
    BEHAVIOUR_FILES,
    rag_behaviour_hash,
    rag_fingerprint,
    ragas_fingerprint,
)


def test_rag_fingerprint_includes_models_and_behaviour_hash(monkeypatch):
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "qwen2.5:3b-instruct")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    fp = rag_fingerprint()
    parts = fp.split("|")
    assert parts[0] == "qwen2.5:3b-instruct"
    assert parts[1] == "nomic-embed-text"
    assert parts[2].startswith("rag:") and len(parts[2]) == len("rag:") + 8


def test_behaviour_hash_is_deterministic_and_hex():
    h1 = rag_behaviour_hash()
    h2 = rag_behaviour_hash()
    assert h1 == h2
    assert len(h1) == 8
    int(h1, 16)  # valid hex


def test_behaviour_files_exist():
    # A dangling behaviour-file path would silently weaken the fingerprint — keep the list honest.
    from atlas_evals.datasets.corpus import REPO_ROOT

    missing = [rel for rel in BEHAVIOUR_FILES if not (REPO_ROOT / rel).exists()]
    assert missing == [], f"behaviour files missing: {missing}"


def test_ragas_fingerprint_format():
    assert ragas_fingerprint().startswith("ragas:")
