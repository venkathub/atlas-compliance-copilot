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
    build_cost_per_request,
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


# --- P7 Task 5: cost/latency-per-request + report-only statistics (D3/ADR-0077, D8/ADR-0082) ---

def _per_case():
    # 12 paired cases per metric: faithfulness (continuous), format/refusal (binary 0/1).
    return {
        "faithfulness": {
            "base": [0.80 + 0.01 * i for i in range(12)],
            "ft": [0.68 + 0.01 * i for i in range(12)],  # consistent ~-0.12 regression
        },
        "format_validity": {"base": [0.0] * 12, "ft": [1.0] * 12},  # big binary jump
        "refusal_correctness": {"base": [1.0, 0.0] * 6, "ft": [1.0, 0.0] * 6},  # no change
    }


def test_cost_per_request_block_shape():
    cpr = build_cost_per_request(
        base_latencies_ms=[100.0, 120.0, 110.0],
        ft_latencies_ms=[130.0, 150.0, 140.0],
        base_cost_units_per_req=0.001,
        ft_cost_units_per_req=0.0011,
        same_gpu="L4",
    )
    assert cpr["same_gpu"] == "L4"
    assert cpr["delta_pct"] == 10.0  # (0.0011-0.001)/0.001*100
    assert cpr["base"]["latency_ms_p50"] == 110.0
    assert set(cpr["ft"]) == {"cost_units_per_req", "latency_ms_p50", "latency_ms_p95"}


def test_cost_delta_pct_zero_when_base_zero():
    cpr = build_cost_per_request(
        base_latencies_ms=[], ft_latencies_ms=[],
        base_cost_units_per_req=0.0, ft_cost_units_per_req=0.0,
    )
    assert cpr["delta_pct"] == 0.0


def test_stats_embedded_without_breaking_base_ft_delta():
    r = build_comparison(
        BASE, FT, model_ids=MODEL_IDS, dataset_size=12, per_case=_per_case(), stats_seed=0,
    )
    for m in METRICS:
        block = r.metrics[m]
        # the gate-critical trio is untouched...
        assert set(("base", "ft", "delta")).issubset(block)
        assert block["delta"] == metric_delta(BASE[m], FT[m])
        # ...and the report-only stats are additive.
        assert "ci95_delta" in block and "p_value" in block and "significant" in block
    assert r.ci_method == "paired_bootstrap_10k"
    assert r.sig_test == "wilcoxon+mcnemar"
    assert r.metrics["faithfulness"]["test"] == "wilcoxon"
    assert r.metrics["format_validity"]["test"] == "mcnemar"


def test_no_stats_when_per_case_absent():
    r = build_comparison(BASE, FT, model_ids=MODEL_IDS, dataset_size=3)
    assert r.ci_method == "" and r.sig_test == ""
    assert "ci95_delta" not in r.metrics["faithfulness"]


def test_extended_comparison_round_trips_and_is_gate_readable():
    cpr = build_cost_per_request(
        base_latencies_ms=[100.0], ft_latencies_ms=[104.0],
        base_cost_units_per_req=0.001, ft_cost_units_per_req=0.00104,
    )
    r = build_comparison(
        BASE, FT, model_ids=MODEL_IDS, dataset_size=12,
        cost_per_request=cpr, per_case=_per_case(),
    )
    raw = r.to_json()
    # the promotion gate reads exactly these paths — assert they exist and are well-typed.
    assert raw["cost"]["delta_pct"] == 4.0
    for m in METRICS:
        assert isinstance(raw["metrics"][m]["ft"], float)
    assert ComparisonResult.from_json(raw) == r


def test_markdown_shows_stats_and_cost_sections():
    cpr = build_cost_per_request(
        base_latencies_ms=[100.0], ft_latencies_ms=[112.0],
        base_cost_units_per_req=0.001, ft_cost_units_per_req=0.00112,
    )
    r = build_comparison(
        BASE, FT, model_ids=MODEL_IDS, dataset_size=12,
        cost_per_request=cpr, per_case=_per_case(),
    )
    md = comparison_markdown(r)
    assert "Statistical rigor" in md
    assert "95% CI" in md
    assert "Serving cost/latency per request" in md
    assert "Cost/req Δ:" in md
