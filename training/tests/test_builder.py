"""Offline, GPU-free tests for the SFT dataset builder + split (P6 Task 5).

Covers chat-format example shape, label carry-through, deterministic reproducible disjoint splits,
split sizes matching planned_split/manifest, and the COMMITTED train.jsonl + val.jsonl integrity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_training.data.builder import (
    SYSTEM_PROMPT,
    SFTExample,
    build_and_write,
    read_jsonl,
    split_dataset,
    to_example,
    write_jsonl,
)
from atlas_training.data.corpus import load_corpus
from atlas_training.data.manifest import load as load_manifest
from atlas_training.data.synth import SyntheticPair, build_seed, planned_split
from atlas_training.data.synth import read_jsonl as read_pairs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def pairs() -> list[SyntheticPair]:
    return build_seed(load_corpus())


def _key(ex: SFTExample) -> tuple[str, str]:
    return (ex.provenance_ref, ex.messages[1]["content"])


# ── example shape ─────────────────────────────────────────────────────────────────────────────────


def test_to_example_shape(pairs):
    ex = to_example(pairs[0])
    roles = [m["role"] for m in ex.messages]
    assert roles == ["system", "user", "assistant"]
    assert ex.messages[0]["content"] == SYSTEM_PROMPT
    assert pairs[0].question in ex.messages[1]["content"]
    assert "[doc:" in ex.messages[1]["content"]  # context marker present
    assert ex.messages[2]["content"] == pairs[0].answer
    assert ex.label == pairs[0].label
    assert ex.provenance_ref == pairs[0].provenance_ref


def test_to_example_rejects_bad_label(pairs):
    bad = SyntheticPair(
        question="q", context="[doc:x] c", answer="a", label="bogus",
        provenance_ref="x", generator="hand-authored",
    )
    with pytest.raises(ValueError, match="unknown label"):
        to_example(bad)


def test_every_example_carries_system_prompt(pairs):
    train, val = split_dataset(pairs, seed=42)
    for ex in train + val:
        assert ex.messages[0]["content"] == SYSTEM_PROMPT


def test_bake_in_uses_minimal_system(pairs):
    from atlas_training.data.builder import MINIMAL_SYSTEM

    train, val = split_dataset(pairs, seed=42, system=MINIMAL_SYSTEM)
    for ex in train + val:
        assert ex.messages[0]["content"] == MINIMAL_SYSTEM
        assert "[doc:" not in ex.messages[0]["content"]  # no citation instruction leaked


# ── deterministic split ─────────────────────────────────────────────────────────────────────────


def test_split_sizes_match_planned(pairs):
    train, val = split_dataset(pairs, seed=42)
    exp_train, exp_val = planned_split(len(pairs))
    assert (len(train), len(val)) == (exp_train, exp_val)


def test_split_reproducible(pairs):
    a = split_dataset(pairs, seed=42)
    b = split_dataset(pairs, seed=42)
    assert [e.to_dict() for e in a[0]] == [e.to_dict() for e in b[0]]
    assert [e.to_dict() for e in a[1]] == [e.to_dict() for e in b[1]]


def test_split_disjoint_and_complete(pairs):
    train, val = split_dataset(pairs, seed=42)
    kt = {_key(e) for e in train}
    kv = {_key(e) for e in val}
    assert kt.isdisjoint(kv)
    assert len(kt) + len(kv) == len(pairs)  # no dropped/duplicated pairs


def test_split_seed_changes_partition(pairs):
    # Different seeds should generally produce a different val membership (sanity, not a guarantee).
    v42 = {_key(e) for e in split_dataset(pairs, seed=42)[1]}
    v7 = {_key(e) for e in split_dataset(pairs, seed=7)[1]}
    assert v42 != v7 or len(pairs) <= 2


# ── jsonl IO ──────────────────────────────────────────────────────────────────────────────────────


def test_jsonl_round_trip(tmp_path, pairs):
    train, _ = split_dataset(pairs, seed=42)
    p = tmp_path / "t.jsonl"
    write_jsonl(train, p)
    assert read_jsonl(p) == train


def test_build_and_write(tmp_path, pairs):
    tp, vp = build_and_write(pairs, seed=42, out_dir=tmp_path)
    assert tp.exists() and vp.exists()
    assert len(read_jsonl(tp)) + len(read_jsonl(vp)) == len(pairs)


# ── committed artifacts ──────────────────────────────────────────────────────────────────────────


def test_committed_splits_match_manifest():
    train = read_jsonl(DATA_DIR / "train.jsonl")
    val = read_jsonl(DATA_DIR / "val.jsonl")
    man = load_manifest(DATA_DIR / "manifest.json")
    assert len(train) == man.split.train
    assert len(val) == man.split.val
    # complete + disjoint vs the committed seed
    seed_pairs = read_pairs(DATA_DIR / "synthetic.jsonl")
    assert len(train) + len(val) == len(seed_pairs)
    kt = {_key(e) for e in train}
    kv = {_key(e) for e in val}
    assert kt.isdisjoint(kv)


def test_committed_splits_regenerate_identically():
    # The committed files must equal a fresh deterministic rebuild from the committed seed (42).
    seed_pairs = read_pairs(DATA_DIR / "synthetic.jsonl")
    train, val = split_dataset(seed_pairs, seed=42)
    assert read_jsonl(DATA_DIR / "train.jsonl") == train
    assert read_jsonl(DATA_DIR / "val.jsonl") == val
