"""Offline, GPU-free tests for synthetic generation (P6 Task 4).

The frontier generator is mocked (no network/secret). Covers: prompt-template sha stability,
generator-seam answer pairs, hand-authored answers/refusals grounded in the real corpus, jsonl
round-trip, deterministic split, and that the COMMITTED seed + manifest validate with grounding.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas_training.data.corpus import load_corpus
from atlas_training.data.manifest import load as load_manifest
from atlas_training.data.manifest import validate as validate_manifest
from atlas_training.data.synth import (
    AUTHORED_ANSWERS,
    AUTHORED_REFUSALS,
    FrontierGenerator,
    Generator,
    SyntheticPair,
    authored_answers,
    authored_refusals,
    build_manifest,
    build_seed,
    excerpt,
    generate_answer_pair,
    planned_split,
    prompt_template_sha,
    provenance_refs,
    read_jsonl,
    write_jsonl,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOC_MARKER = re.compile(r"\[doc:[A-Za-z0-9_-]+\]")


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


class FakeGenerator:
    """Deterministic in-memory generator — the mockable seam (no network)."""

    model_id = "fake-teacher-v1"

    def __init__(self, reply: str = "The answer is 42 [doc:financebench_id_03029]."):
        self.reply = reply
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


# ── prompt template + excerpt ─────────────────────────────────────────────────────────────────────


def test_prompt_template_sha_stable():
    sha = prompt_template_sha()
    assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert prompt_template_sha() == sha  # deterministic


def test_excerpt_truncates():
    assert excerpt("a b c", limit=100) == "a b c"
    long = "word " * 500
    out = excerpt(long, limit=50)
    assert len(out) <= 52 and out.endswith("…")


# ── generator seam ────────────────────────────────────────────────────────────────────────────────


def test_fake_generator_satisfies_protocol():
    assert isinstance(FakeGenerator(), Generator)


def test_generate_answer_pair_uses_generator_and_tags_provenance(corpus):
    doc = corpus.resolve("financebench_id_03029")
    gen = FakeGenerator()
    pair = generate_answer_pair(doc, "What was FY2018 capex?", gen)
    assert pair.label == "answer"
    assert pair.provenance_ref == "financebench_id_03029"
    assert pair.generator == "fake-teacher-v1"
    assert pair.context.startswith("[doc:financebench_id_03029]")
    assert len(gen.calls) == 1
    assert "QUESTION: What was FY2018 capex?" in gen.calls[0]


# ── hand-authored seed ──────────────────────────────────────────────────────────────────────────


def test_authored_answers_cited_and_grounded(corpus):
    pairs = authored_answers(corpus)
    assert len(pairs) == len(AUTHORED_ANSWERS)
    for p in pairs:
        assert p.label == "answer"
        assert DOC_MARKER.search(p.answer), f"answer missing [doc:ID]: {p.answer}"
        assert f"[doc:{p.provenance_ref}]" in p.answer
        corpus.resolve(p.provenance_ref)  # grounded in trusted corpus


def test_authored_refusals_grounded_and_unfabricated(corpus):
    pairs = authored_refusals(corpus)
    assert len(pairs) == len(AUTHORED_REFUSALS)
    for p in pairs:
        assert p.label == "refusal"
        assert "can't answer" in p.answer.lower() or "cannot answer" in p.answer.lower()
        assert not DOC_MARKER.search(p.answer)  # a refusal must not fabricate a citation
        corpus.resolve(p.provenance_ref)


def test_build_seed_counts(corpus):
    pairs = build_seed(corpus)
    assert len(pairs) == len(AUTHORED_ANSWERS) + len(AUTHORED_REFUSALS)


# ── jsonl IO + split ────────────────────────────────────────────────────────────────────────────


def test_jsonl_round_trip(tmp_path, corpus):
    pairs = build_seed(corpus)
    p = tmp_path / "s.jsonl"
    write_jsonl(pairs, p)
    assert read_jsonl(p) == pairs


@pytest.mark.parametrize(
    "n,expected",
    [(0, (0, 0)), (1, (1, 0)), (5, (4, 1)), (10, (8, 2)), (20, (16, 4))],
)
def test_planned_split_deterministic(n, expected):
    assert planned_split(n) == expected


# ── manifest assembly + committed seed ────────────────────────────────────────────────────────────


def test_build_manifest_validates_with_grounding(corpus):
    pairs = build_seed(corpus)
    man = build_manifest(
        pairs, corpus, dataset_version="p6-v1", seed=42,
        generator_model="hand-authored", generator_provider="internal",
    )
    validate_manifest(man, corpus, synthetic_refs=provenance_refs(pairs))
    assert man.synthetic.count == len(pairs)
    assert man.synthetic.prompt_template_sha == prompt_template_sha()


def test_committed_seed_present_and_valid(corpus):
    pairs = read_jsonl(DATA_DIR / "synthetic.jsonl")
    assert pairs, "committed data/synthetic.jsonl is empty"
    assert all(isinstance(p, SyntheticPair) for p in pairs)
    man = load_manifest(DATA_DIR / "manifest.json")
    validate_manifest(man, corpus, synthetic_refs=provenance_refs(pairs))
    assert man.synthetic.count == len(pairs)
    assert man.split.train + man.split.val == len(pairs)


# ── FrontierGenerator env wiring (no openai import / no network) ──────────────────────────────────


def test_frontier_from_env_requires_model(monkeypatch):
    monkeypatch.delenv("ATLAS_SYNTH_GENERATOR_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="ATLAS_SYNTH_GENERATOR_MODEL"):
        FrontierGenerator.from_env()


def test_frontier_from_env_reads_config(monkeypatch):
    monkeypatch.setenv("ATLAS_SYNTH_GENERATOR_MODEL", "teacher-x")
    monkeypatch.setenv("ATLAS_SYNTH_BASE_URL", "https://example/v1")
    monkeypatch.setenv("ATLAS_SYNTH_API_KEY", "sk-test")
    gen = FrontierGenerator.from_env()
    assert gen.model_id == "teacher-x"
    assert gen.base_url == "https://example/v1"
    assert gen.api_key == "sk-test"


# ── self-hosted-teacher generation at scale ──────────────────────────────────────────────────────


class FakeQAGenerator:
    """Returns a fixed JSON array of QA pairs (teacher seam, no network)."""

    model_id = "ollama-teacher"

    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        return self.reply


def test_parse_qa_array_extracts_pairs():
    from atlas_training.data.synth import parse_qa_array

    txt = 'sure!\n[{"question": "Q1?", "answer": "A1"}, {"question":"Q2?","answer":"A2"}] done'
    out = parse_qa_array(txt)
    assert [o["question"] for o in out] == ["Q1?", "Q2?"]


def test_parse_qa_array_handles_garbage():
    from atlas_training.data.synth import parse_qa_array

    assert parse_qa_array("no json here") == []
    assert parse_qa_array("[not valid json") == []


def test_enforce_citation_strips_and_appends():
    from atlas_training.data.synth import enforce_citation

    # hallucinated cross-doc citation removed; correct one appended
    out = enforce_citation("Revenue was $10M [doc:wrong_id]", "fb_a")
    assert out == "Revenue was $10M [doc:fb_a]."
    assert "[doc:wrong_id]" not in out
    assert enforce_citation("", "fb_a") == ""


def test_generate_doc_pairs_grounded_and_format_valid(corpus):
    from atlas_training.data.synth import generate_doc_pairs

    doc = corpus.resolve("financebench_id_03029")
    gen = FakeQAGenerator(
        '[{"question":"What was capex?","answer":"It was $1,577M [doc:hallucinated]"},'
        '{"question":"What was capex?","answer":"dup question"},'
        '{"question":"Net income?","answer":"$5,363M"}]'
    )
    pairs = generate_doc_pairs(doc, 6, gen)
    # dedup by question (2 unique) and every answer cites ONLY this doc
    assert len(pairs) == 2
    for p in pairs:
        assert p.label == "answer"
        assert p.provenance_ref == "financebench_id_03029"
        assert "[doc:financebench_id_03029]" in p.answer
        assert "[doc:hallucinated]" not in p.answer


def test_templated_refusals_grounded(corpus):
    from atlas_training.data.synth import templated_refusals

    refs = templated_refusals(corpus, per_doc=1)
    assert len(refs) == len(corpus)
    for r in refs:
        assert r.label == "refusal"
        assert "can't answer" in r.answer.lower()
        corpus.resolve(r.provenance_ref)


def test_build_generated_dataset(corpus):
    from atlas_training.data.synth import build_generated_dataset

    gen = FakeQAGenerator('[{"question":"Q?","answer":"A"}]')
    pairs = build_generated_dataset(corpus, gen, answers_per_doc=1, refusals_per_doc=1)
    n_ans = sum(1 for p in pairs if p.label == "answer")
    n_ref = sum(1 for p in pairs if p.label == "refusal")
    assert n_ans == len(corpus)  # 1 answer/doc
    assert n_ref == len(corpus)  # 1 refusal/doc
    # all grounded in the trusted corpus
    for p in pairs:
        corpus.resolve(p.provenance_ref)
