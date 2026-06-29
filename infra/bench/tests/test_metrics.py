"""Pure-metric tests (no GPU, no network)."""

from __future__ import annotations

from atlas_bench.metrics import (
    RequestResult,
    cost_per_million_tokens,
    percentile,
    summarize,
)


def test_percentile_basic_and_edges():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 40.0
    assert percentile(values, 50) == 25.0  # linear interp midpoint
    assert percentile([], 90) == 0.0
    assert percentile([7.0], 99) == 7.0


def test_summarize_throughput_uses_wall_clock_not_request_sum():
    # 4 successful requests, 200 output tokens total, in a 2s wall window.
    results = [
        RequestResult(ok=True, latency_s=1.5, ttft_s=0.2, output_tokens=50) for _ in range(4)
    ]
    bp = summarize(concurrency=4, wall_s=2.0, results=results)
    assert bp.requests == 4
    assert bp.errors == 0
    assert bp.output_tokens == 200
    assert bp.output_tokens_per_s == 100.0  # 200 / 2s, NOT divided by per-request latency
    assert bp.requests_per_s == 2.0  # 4 ok / 2s


def test_summarize_excludes_failures_from_latency_but_counts_errors():
    results = [
        RequestResult(ok=True, latency_s=1.0, ttft_s=0.1, output_tokens=10),
        RequestResult(ok=False, latency_s=99.0, error="HTTP 500"),
    ]
    bp = summarize(concurrency=2, wall_s=1.0, results=results)
    assert bp.errors == 1
    assert bp.error_rate == 0.5
    # the 99s failure must NOT pollute latency percentiles
    assert bp.e2e_p99_ms == 1000.0
    assert bp.output_tokens == 10  # failed request contributes no tokens


def test_summarize_empty_is_safe():
    bp = summarize(concurrency=1, wall_s=0.0, results=[])
    assert bp.requests == 0
    assert bp.error_rate == 0.0
    assert bp.output_tokens_per_s == 0.0


def test_cost_per_million_tokens_matches_hand_calc():
    # 100 tok/s -> 360_000 tok/hr; at 41/hr -> 41 / 0.36 = 113.8889 per 1M
    assert cost_per_million_tokens(41.0, 100.0) == 113.8889
    assert cost_per_million_tokens(41.0, 0.0) == float("inf")
