"""Report tests: JSON round-trip + Markdown comparison (pure offline)."""

from __future__ import annotations

import json

from atlas_bench.metrics import BenchPoint
from atlas_bench.report import BenchRun, compare_markdown, peak_throughput


def _point(concurrency: int, tok_s: float, p99_ms: float = 1000.0) -> BenchPoint:
    return BenchPoint(
        concurrency=concurrency, requests=10, errors=0, error_rate=0.0, wall_s=5.0,
        requests_per_s=2.0, output_tokens=int(tok_s * 5), output_tokens_per_s=tok_s,
        ttft_p50_ms=100.0, ttft_p90_ms=150.0, ttft_p99_ms=200.0,
        e2e_p50_ms=500.0, e2e_p90_ms=800.0, e2e_p99_ms=p99_ms,
    )


def _run(backend: str, points) -> BenchRun:
    return BenchRun(
        backend=backend, model="qwen2.5:7b", gpu="L4", gpu_cost_per_hour=41.0, points=points,
    )


def test_json_round_trip(tmp_path):
    run = _run("vllm", [_point(1, 30.0), _point(8, 180.0)])
    path = tmp_path / "vllm.json"
    run.write_json(str(path))
    data = json.loads(path.read_text())
    assert data["backend"] == "vllm"
    assert len(data["points"]) == 2
    # points reconstruct into BenchPoint dataclasses
    pts = [BenchPoint(**p) for p in data["points"]]
    assert pts[1].output_tokens_per_s == 180.0


def test_peak_throughput_picks_highest_tok_s():
    run = _run("vllm", [_point(1, 30.0), _point(8, 180.0), _point(16, 160.0)])
    peak = peak_throughput(run)
    assert peak.concurrency == 8


def test_compare_markdown_has_ratio_and_levels():
    ollama = _run("ollama", [_point(1, 28.0), _point(8, 40.0)])
    vllm = _run("vllm", [_point(1, 30.0), _point(8, 180.0)])
    md = compare_markdown([ollama, vllm])
    assert "Concurrency" in md
    assert "ollama" in md and "vllm" in md
    # peak ratio: vllm 180 / ollama 40 = 4.5x
    assert "4.50×" in md
    # both concurrency levels present as rows
    assert "| 8 |" in md


def test_compare_markdown_handles_missing_level():
    ollama = _run("ollama", [_point(1, 28.0)])
    vllm = _run("vllm", [_point(1, 30.0), _point(8, 180.0)])
    md = compare_markdown([ollama, vllm])
    assert "—" in md  # ollama has no c=8 cell
