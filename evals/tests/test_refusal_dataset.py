"""Tests for the labeled refusal-subset loader (P6 Task 10a)."""

from __future__ import annotations

import pytest

from atlas_evals.datasets.refusal import DEFAULT_PATH, load_refusal
from atlas_evals.metrics.refusal import RefusalCase, score


def test_committed_subset_loads_and_validates():
    cases = load_refusal()
    assert len(cases) >= 5
    assert all(isinstance(c, RefusalCase) for c in cases)
    # both lanes present: refuse + answerable controls
    assert any(c.should_refuse for c in cases)
    assert any(not c.should_refuse for c in cases)


def test_ids_unique():
    cases = load_refusal()
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))


def test_default_path_points_at_committed_file():
    assert DEFAULT_PATH.name == "refusal.jsonl"
    assert DEFAULT_PATH.exists()


def test_subset_is_scorable():
    # Sanity: a correct response on each case scores True (the metric wiring is coherent).
    cases = load_refusal()
    for c in cases:
        out = (
            "I can't answer that from the provided sources."
            if c.should_refuse
            else "The figure is $1,577 million [doc:financebench_id_03029]."
        )
        assert score(c, out) is True


def test_loader_rejects_bad_clearance(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(
        '{"id": "x", "question": "q?", "should_refuse": true, "clearance": "top-secret"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid clearance"):
        load_refusal(p)


def test_loader_rejects_duplicate_id(tmp_path):
    p = tmp_path / "dup.jsonl"
    p.write_text(
        '{"id": "x", "question": "q?", "should_refuse": true}\n'
        '{"id": "x", "question": "q2?", "should_refuse": false}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate case id"):
        load_refusal(p)


def test_loader_rejects_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no refusal cases"):
        load_refusal(p)
