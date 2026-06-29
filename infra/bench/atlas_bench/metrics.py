"""Pure metric math for the serving benchmark (no I/O, fully unit-testable offline).

A benchmark run is a list of per-request samples (``RequestResult``) gathered at one
concurrency level. ``summarize`` folds those samples + the wall-clock window into a single
``BenchPoint``. The aggregate throughput numbers (req/s, tok/s) deliberately use the
**wall-clock window**, not per-request sums, because that is what continuous batching
actually changes: many requests overlap in time, so output_tokens / wall_seconds is the
honest system throughput.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass
class RequestResult:
    """One completed (or failed) request sample."""

    ok: bool
    latency_s: float  # end-to-end: send -> last token
    ttft_s: float | None = None  # time-to-first-token (None if non-streaming/failed)
    output_tokens: int = 0
    error: str | None = None


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0,100]); empty -> 0.0.

    Matches the common "p90/p99 latency" convention; not NumPy-dependent on purpose so the
    harness stays stdlib-only outside the live client.
    """
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    ordered = sorted(values)
    rank = (p / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


@dataclass
class BenchPoint:
    """Summary of one concurrency level."""

    concurrency: int
    requests: int
    errors: int
    error_rate: float
    wall_s: float
    requests_per_s: float
    output_tokens: int
    output_tokens_per_s: float
    ttft_p50_ms: float
    ttft_p90_ms: float
    ttft_p99_ms: float
    e2e_p50_ms: float
    e2e_p90_ms: float
    e2e_p99_ms: float

    def as_dict(self) -> dict:
        return asdict(self)


def summarize(concurrency: int, wall_s: float, results: list[RequestResult]) -> BenchPoint:
    """Fold raw samples + the measured wall-clock window into a BenchPoint.

    Latency percentiles are computed over **successful** requests only (a failed request's
    latency is meaningless), while throughput divides successful work by the wall window.
    """
    ok = [r for r in results if r.ok]
    errors = len(results) - len(ok)
    wall = wall_s if wall_s > 0 else 1e-9

    e2e_ms = [r.latency_s * 1000.0 for r in ok]
    ttft_ms = [r.ttft_s * 1000.0 for r in ok if r.ttft_s is not None]
    out_tokens = sum(r.output_tokens for r in ok)

    return BenchPoint(
        concurrency=concurrency,
        requests=len(results),
        errors=errors,
        error_rate=(errors / len(results)) if results else 0.0,
        wall_s=round(wall_s, 4),
        requests_per_s=round(len(ok) / wall, 3),
        output_tokens=out_tokens,
        output_tokens_per_s=round(out_tokens / wall, 2),
        ttft_p50_ms=round(percentile(ttft_ms, 50), 1),
        ttft_p90_ms=round(percentile(ttft_ms, 90), 1),
        ttft_p99_ms=round(percentile(ttft_ms, 99), 1),
        e2e_p50_ms=round(percentile(e2e_ms, 50), 1),
        e2e_p90_ms=round(percentile(e2e_ms, 90), 1),
        e2e_p99_ms=round(percentile(e2e_ms, 99), 1),
    )


def cost_per_million_tokens(gpu_cost_per_hour: float, output_tokens_per_s: float) -> float:
    """Derive *measured* cost per 1M output tokens from GPU price and throughput.

    This is the empirical replacement for ADR-0040's synthetic cost-units: instead of
    assuming a throughput, we plug in the tok/s the benchmark actually sustained.
    """
    if output_tokens_per_s <= 0:
        return float("inf")
    tokens_per_hour = output_tokens_per_s * 3600.0
    return round(gpu_cost_per_hour / (tokens_per_hour / 1_000_000.0), 4)
