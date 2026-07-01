"""Offline, GPU-free tests for the trusted-corpus loader (P6 Task 2).

Loads the *real* committed corpus (no network/GPU) and proves every Layer-1 manifest id and
every Layer-2 doc resolves, clearances are valid, and unknown ids fail fast (the LLM04 guard).
A tiny tmp fixture corpus proves the root override (no hardcoded path).
"""

from __future__ import annotations

import json

import pytest

from atlas_training.data.corpus import (
    CLEARANCES,
    DEFAULT_CORPUS_DIR,
    Corpus,
    CorpusError,
    TrustedDoc,
    load_corpus,
)

LAYER1_MANIFEST = DEFAULT_CORPUS_DIR / "layer1" / "manifest.json"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus()


# ── real committed corpus ───────────────────────────────────────────────────────────────────────


def test_layer1_every_manifest_id_resolves(corpus):
    manifest = json.loads(LAYER1_MANIFEST.read_text(encoding="utf-8"))
    ids = [d["financebench_id"] for d in manifest["documents"]]
    assert len(corpus.by_layer(1)) == len(ids)
    for fid in ids:
        doc = corpus.resolve(fid)
        assert doc.layer == 1
        assert doc.text.strip()
        assert doc.source == f"financebench:{fid}"


def test_layer2_every_md_resolves(corpus):
    md_files = sorted((DEFAULT_CORPUS_DIR / "layer2").glob("*.md"))
    assert len(corpus.by_layer(2)) == len(md_files)
    for md in md_files:
        # doc_id defaults to the file stem when front-matter omits it; here it is present.
        assert md.stem in corpus
        doc = corpus.resolve(md.stem)
        assert doc.layer == 2
        assert doc.source == f"layer2:{md.stem}"
        assert doc.text.strip()


def test_all_clearances_valid(corpus):
    for doc in corpus.docs.values():
        assert doc.clearance in CLEARANCES


def test_layer2_carries_front_matter_metadata(corpus):
    doc = corpus.resolve("l2-northwind-aml-exceptions-2026q2")
    assert doc.clearance == "compliance"
    assert doc.metadata.get("doc_type") == "aml_exception_summary"
    assert "front-matter" not in doc.text  # body only, delimiter stripped
    assert doc.text.startswith("#")


def test_total_count_is_both_layers(corpus):
    assert len(corpus) == len(corpus.by_layer(1)) + len(corpus.by_layer(2))
    assert len(corpus) >= 24


def test_ids_and_contains(corpus):
    some = next(iter(corpus.docs))
    assert some in corpus
    assert some in corpus.ids()
    assert corpus.get(some) is not None
    assert corpus.get("nope") is None


def test_resolve_unknown_id_raises(corpus):
    with pytest.raises(CorpusError, match="not in trusted corpus"):
        corpus.resolve("financebench_id_does_not_exist")


# ── root override (proves no hardcoded path) ─────────────────────────────────────────────────────


def _write_min_corpus(root):
    l1 = root / "layer1"
    l2 = root / "layer2"
    l1.mkdir(parents=True)
    l2.mkdir(parents=True)
    (l1 / "doc_a.txt").write_text("Revenue was $10M in FY2024.", encoding="utf-8")
    (l1 / "manifest.json").write_text(
        json.dumps(
            {
                "documents": [
                    {"file": "doc_a.txt", "financebench_id": "fb_a", "clearance": "public",
                     "doc_name": "ACME_2024_10K"}
                ]
            }
        ),
        encoding="utf-8",
    )
    (l2 / "l2-memo.md").write_text(
        "---\ndoc_id: l2-memo\nclearance: compliance\ndoc_type: memo\n---\n\n"
        "# Memo\n\nBody text.\n",
        encoding="utf-8",
    )


def test_custom_root_override(tmp_path):
    _write_min_corpus(tmp_path)
    c = load_corpus(tmp_path)
    assert len(c) == 2
    a = c.resolve("fb_a")
    assert isinstance(a, TrustedDoc)
    assert a.layer == 1 and a.clearance == "public"
    assert a.metadata.get("doc_name") == "ACME_2024_10K"
    m = c.resolve("l2-memo")
    assert m.layer == 2 and m.clearance == "compliance"
    assert m.text == "# Memo\n\nBody text."


def test_env_var_override(tmp_path, monkeypatch):
    _write_min_corpus(tmp_path)
    monkeypatch.setenv("ATLAS_CORPUS_ROOT", str(tmp_path))
    c = load_corpus()
    assert "fb_a" in c and "l2-memo" in c


# ── malformed-input guards ───────────────────────────────────────────────────────────────────────


def test_missing_root_raises(tmp_path):
    with pytest.raises(CorpusError, match="corpus root not found"):
        load_corpus(tmp_path / "nope")


def test_layer1_missing_file_raises(tmp_path):
    (tmp_path / "layer1").mkdir()
    (tmp_path / "layer2").mkdir()
    (tmp_path / "layer1" / "manifest.json").write_text(
        json.dumps({"documents": [{"file": "ghost.txt", "financebench_id": "x",
                                    "clearance": "public"}]}),
        encoding="utf-8",
    )
    with pytest.raises(CorpusError, match="missing file"):
        load_corpus(tmp_path)


def test_layer2_missing_front_matter_raises(tmp_path):
    _write_min_corpus(tmp_path)
    (tmp_path / "layer2" / "bad.md").write_text("no front matter here", encoding="utf-8")
    with pytest.raises(CorpusError, match="front-matter"):
        load_corpus(tmp_path)


def test_invalid_clearance_raises(tmp_path):
    _write_min_corpus(tmp_path)
    (tmp_path / "layer2" / "bad.md").write_text(
        "---\ndoc_id: bad\nclearance: top-secret\n---\n\nBody.\n", encoding="utf-8"
    )
    with pytest.raises(CorpusError, match="invalid clearance"):
        load_corpus(tmp_path)
