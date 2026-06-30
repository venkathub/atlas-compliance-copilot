"""Offline, GPU-free tests for the base-vs-FT comparison report generator (P6 Task 10a).

Pure arithmetic + formatting on fixture score dicts — no GPU, no evals/model import.
"""

from __future__ import annotations

import json

import pytest

from atlas_training.report import (
    METRICS,
    ComparisonResult,
    build_comparison,
    comparison_markdown,
    metric_delta,
    write_comparison,
)

BASE = {"faithfulness": 0.70, "format_validity": 0.55, "refusal_correctness": 0.60}
FT = {"faithfulness": 0.72, "format_validity": 0.97, "refusal_correctness": 0.80}
MODEL_IDS = {"base": "Qwen/Qwen2.5-7B-Instruct", "ft": "hf://u/atlas-citation-adapter@rev9"}
COST = {"rate_per_hour": 50.0, "currency": "INR", "wall_seconds": 3600.0, "cost": 50.0}


@pytest.fixture
def result() -> ComparisonResult:
    return build_comparison(
        BASE, FT, model_ids=MODEL_IDS, dataset_size=40, training_cost=COST,
        git_sha="abc1234", recorded_at="2026-06-30T00:00:00+00:00",
    )


def test_metric_delta():
    assert metric_delta(0.70, 0.72) == 0.02
    assert metric_delta(0.60, 0.60) == 0.0
    assert metric_delta(0.97, 0.55) == -0.42


def test_build_comparison_computes_deltas(result):
    assert set(result.metrics) == set(METRICS)
    assert result.metrics["format_validity"] == {"base": 0.55, "ft": 0.97, "delta": 0.42}
    assert result.metrics["faithfulness"]["delta"] == 0.02
    assert result.dataset_size == 40
    assert result.model_ids == MODEL_IDS


def test_build_comparison_requires_all_metrics():
    with pytest.raises(ValueError, match="missing metric scores"):
        build_comparison(
            {"faithfulness": 0.7}, FT, model_ids=MODEL_IDS, dataset_size=10
        )


def test_json_round_trip(result):
    assert ComparisonResult.from_json(result.to_json()) == result


def test_markdown_contains_table_and_provenance(result):
    md = comparison_markdown(result)
    assert "| Metric | base | ft | Δ |" in md
    for m in METRICS:
        assert m in md
    assert "+0.4200" in md  # format_validity delta, signed
    assert "50.0 INR" in md  # training cost
    assert "abc1234" in md  # git sha
    assert "hf://u/atlas-citation-adapter@rev9" in md  # ft model id


def test_write_comparison(tmp_path, result):
    jp, mp = write_comparison(result, tmp_path)
    assert jp.exists() and mp.exists()
    loaded = ComparisonResult.from_json(json.loads(jp.read_text()))
    assert loaded == result
    assert "base vs fine-tuned" in mp.read_text()


def test_default_git_sha_and_timestamp_filled():
    r = build_comparison(BASE, FT, model_ids=MODEL_IDS, dataset_size=5)
    assert r.git_sha  # current_git_sha() or "unknown"
    assert r.recorded_at  # iso timestamp
