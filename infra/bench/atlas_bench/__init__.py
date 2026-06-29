"""Atlas serving benchmark harness.

Measures **serving** characteristics (throughput, latency, derived cost) of any
OpenAI-compatible chat endpoint under a concurrency sweep, so Ollama and vLLM can be
compared on the *same* GPU with the *same* model. See ADR-0067 + infra/bench/README.md.

Design split (so unit tests need no GPU/network):
  - metrics.py  pure stats: percentiles, per-level summary (BenchPoint).
  - runner.py   async load generator; takes an injectable ``send`` coroutine.
  - client.py   the real httpx streaming client (live runs only).
  - report.py   JSON + Markdown comparison table.
"""

from atlas_bench.metrics import BenchPoint, RequestResult, percentile, summarize
from atlas_bench.runner import run_load, run_sweep

__all__ = [
    "BenchPoint",
    "RequestResult",
    "percentile",
    "summarize",
    "run_load",
    "run_sweep",
]
