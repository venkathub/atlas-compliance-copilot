"""Offline, GPU-free tests for the provenance manifest (P6 Task 3).

Covers build/round-trip/save+load and the trusted-corpus-only `validate` guard: source ids must
resolve in the real committed corpus; rejects unknown ids, count mismatch, bad grounded_in,
synthetic count mismatch, and an ungrounded synthetic ref.
"""

from __future__ import annotations

import pytest

from atlas_training.data.corpus import load_corpus
from atlas_training.data.manifest import (
    GROUNDED_INVARIANT,
    Manifest,
    ManifestError,
    Source,
    Split,
    SyntheticMeta,
    build,
    from_dict,
    listed_source_ids,
    load,
    save,
    validate,
)


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture
def good_manifest(corpus) -> Manifest:
    fb_ids = [d.doc_id for d in corpus.by_layer(1)][:3]
    l2_ids = [d.doc_id for d in corpus.by_layer(2)][:2]
    return build(
        dataset_version="p6-v1",
        seed=42,
        sources=[
            Source(kind="financebench", license="CC-BY-NC-4.0", count=len(fb_ids),
                   ids=tuple(fb_ids)),
            Source(kind="layer2_overlay", license="authored-internal", count=len(l2_ids),
                   docs=tuple(l2_ids)),
        ],
        synthetic=SyntheticMeta(
            generator_model="frontier-x", generator_provider="prov",
            prompt_template_sha="abc123", count=5, answer_pairs=3, refusal_pairs=2,
        ),
        split=Split(train=4, val=1),
        git_sha="deadbeef",
    )


# ── build / serialize round-trip ─────────────────────────────────────────────────────────────────


def test_build_sets_defaults(corpus):
    m = build(
        dataset_version="p6-v1", seed=42,
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=0)],
        synthetic=SyntheticMeta("g", "p", "sha", 0, 0, 0),
        split=Split(train=0, val=0),
    )
    assert m.generated_at  # ISO timestamp filled in
    assert m.git_sha  # current_git_sha() or "unknown"
    assert m.synthetic.grounded_in == GROUNDED_INVARIANT


def test_round_trip_dict(good_manifest):
    assert from_dict(good_manifest.to_dict()) == good_manifest


def test_save_load(tmp_path, good_manifest):
    p = tmp_path / "manifest.json"
    save(good_manifest, p)
    assert load(p) == good_manifest


def test_to_dict_omits_empty_id_lists(good_manifest):
    raw = good_manifest.to_dict()
    fb = next(s for s in raw["sources"] if s["kind"] == "financebench")
    l2 = next(s for s in raw["sources"] if s["kind"] == "layer2_overlay")
    assert "ids" in fb and "docs" not in fb
    assert "docs" in l2 and "ids" not in l2


def test_listed_source_ids(good_manifest):
    ids = listed_source_ids(good_manifest)
    assert len(ids) == 5
    for s in good_manifest.sources:
        for m in s.members():
            assert m in ids


def test_from_dict_malformed_raises():
    with pytest.raises(ManifestError, match="malformed manifest"):
        from_dict({"dataset_version": "x"})  # missing keys


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(ManifestError, match="not found"):
        load(tmp_path / "nope.json")


# ── validate: happy path + guards ────────────────────────────────────────────────────────────────


def test_validate_ok(good_manifest, corpus):
    validate(good_manifest, corpus)  # no raise


def test_validate_unknown_source_id_raises(good_manifest, corpus):
    bad = build(
        dataset_version="p6-v1", seed=42,
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=1,
                        ids=("financebench_id_ghost",))],
        synthetic=good_manifest.synthetic, split=good_manifest.split,
    )
    with pytest.raises(ManifestError, match="not in trusted corpus"):
        validate(bad, corpus)


def test_validate_count_mismatch_raises(good_manifest, corpus):
    fb = [d.doc_id for d in corpus.by_layer(1)][:2]
    bad = build(
        dataset_version="p6-v1", seed=42,
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=5, ids=tuple(fb))],
        synthetic=good_manifest.synthetic, split=good_manifest.split,
    )
    with pytest.raises(ManifestError, match="count="):
        validate(bad, corpus)


def test_validate_bad_grounded_in_raises(corpus):
    fb = [d.doc_id for d in corpus.by_layer(1)][:1]
    bad = build(
        dataset_version="p6-v1", seed=42,
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=1, ids=tuple(fb))],
        synthetic=SyntheticMeta("g", "p", "sha", 0, 0, 0, grounded_in="anything-goes"),
        split=Split(train=0, val=0),
    )
    with pytest.raises(ManifestError, match="grounded_in"):
        validate(bad, corpus)


def test_validate_synthetic_count_mismatch_raises(corpus):
    fb = [d.doc_id for d in corpus.by_layer(1)][:1]
    bad = build(
        dataset_version="p6-v1", seed=42,
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=1, ids=tuple(fb))],
        synthetic=SyntheticMeta("g", "p", "sha", count=9, answer_pairs=3, refusal_pairs=2),
        split=Split(train=0, val=0),
    )
    with pytest.raises(ManifestError, match="synthetic.count"):
        validate(bad, corpus)


def test_validate_seed_must_be_int(corpus):
    fb = [d.doc_id for d in corpus.by_layer(1)][:1]
    bad = build(
        dataset_version="p6-v1", seed=True,  # bool is not a valid seed
        sources=[Source(kind="financebench", license="CC-BY-NC-4.0", count=1, ids=tuple(fb))],
        synthetic=SyntheticMeta("g", "p", "sha", 0, 0, 0), split=Split(train=0, val=0),
    )
    with pytest.raises(ManifestError, match="seed must be an int"):
        validate(bad, corpus)


def test_validate_synthetic_refs_grounded(good_manifest, corpus):
    allowed = list(listed_source_ids(good_manifest))
    # all refs grounded -> ok
    validate(good_manifest, corpus, synthetic_refs=[allowed[0], allowed[1]])
    # one ungrounded ref -> raises
    with pytest.raises(ManifestError, match="non-listed source"):
        validate(good_manifest, corpus, synthetic_refs=[allowed[0], "l2-not-a-listed-doc"])
