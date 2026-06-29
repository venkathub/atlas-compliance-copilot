# infra/bench — Atlas serving benchmark (Ollama vs vLLM)

**Purpose.** Measure and compare the *serving* characteristics — throughput, latency, and
**measured** cost — of any OpenAI-compatible chat endpoint under a concurrency sweep, so
Ollama and vLLM can be judged on the **same GPU with the same model family**. This is the
evidence behind ADR-0067 ("add vLLM as a production serving profile alongside Ollama") and
the `docs/PORTFOLIO.md` bullet.

It exists because Atlas had per-request latency telemetry and a *synthetic* cost-units table
(ADR-0040, GPU ₹/hr ÷ an *assumed* throughput) but no way to measure throughput under load.
This harness replaces the assumption with a number.

## Why this matters (the story)
Ollama is a great single-user dev server; vLLM is a production inference server. The
difference only shows up **under concurrency**: vLLM's PagedAttention + continuous batching
keep many requests in flight, so aggregate tok/s climbs as load rises, while a single-stream
server plateaus and its tail latency explodes. This harness makes that crossover visible and
turns it into ₹/1M-tokens.

## Architecture
```
__main__.py   CLI: `run` (live, GPU) and `compare` (offline post-processing)
runner.py     async load generator; concurrency sweep; injectable `send` coroutine
client.py     httpx streaming client for /v1/chat/completions (TTFT, token usage) — live only
metrics.py    pure stats: percentiles, BenchPoint, summarize, cost_per_million_tokens
report.py     BenchRun JSON + Markdown comparison table
```
The split is deliberate: **metrics/runner/report are pure stdlib and fully unit-tested with
no GPU, no network, no model server.** Only `client.py` needs `httpx`, and only `run` needs a
live endpoint. The runner takes an injectable `send` so tests and the live client share the
exact same orchestration.

## Setup
```bash
cd infra/bench
uv sync            # installs httpx + pytest
```

## Run the benchmark (GPU on)
Both backends speak `POST /v1/chat/completions` with SSE streaming, so the **same command**
works against either — only `--backend`/`--base-url` change.

```bash
# 1) Current Ollama endpoint
uv run python -m atlas_bench run \
    --backend ollama --base-url "$OLLAMA_BASE_URL" --model qwen2.5:7b-instruct \
    --gpu L4 --gpu-cost-per-hour 41 \
    --concurrency 1,4,8,16,32 --requests-per-level 60 --warmup 4 \
    --notes "GGUF Q4_K_M" \
    --out results/ollama-L4.json

# 2) vLLM serving the comparable model on the SAME GPU (see infra vLLM bring-up)
uv run python -m atlas_bench run \
    --backend vllm --base-url http://<gpu-host>:8000 --model Qwen2.5-7B-Instruct-AWQ \
    --gpu L4 --gpu-cost-per-hour 41 \
    --concurrency 1,4,8,16,32 --requests-per-level 60 --warmup 4 \
    --notes "AWQ 4-bit" \
    --out results/vllm-L4.json

# 3) Render the comparison table (offline)
uv run python -m atlas_bench compare results/ollama-L4.json results/vllm-L4.json \
    --out results/COMPARISON.md
```

Run it under the fail-safe GPU lifecycle so the GPU is always paused afterwards:
```bash
uv --directory infra/gpu run python -m atlas_gpu run -- \
    bash -c 'cd infra/bench && uv run python -m atlas_bench run --backend ollama ...'
```

## Metrics & methodology
- **Throughput** = output tokens / **wall-clock window** (not per-request sums) — this is the
  honest system throughput, and exactly what batching changes.
- **TTFT** = time to first streamed content token; **e2e** = send → last token. Percentiles
  (p50/p90/p99) are over **successful** requests only; failures are counted separately in
  `error_rate`.
- **Warmup** requests are issued untimed so model load / cold caches don't skew p99.
- **Cost / 1M tokens** = `gpu_cost_per_hour ÷ (tok/s × 3600 ÷ 1e6)` — the empirical
  replacement for ADR-0040's synthetic cost-units.
- **Token accounting**: prefers server-reported `usage.completion_tokens` (vLLM via
  `stream_options.include_usage`); falls back to a whitespace-word proxy, flagged as
  `token_accounting: proxy` in the output.

## ⚠️ Fairness caveat (read before quoting numbers)
This is **not** a perfectly apples-to-apples comparison and the report says so:
- Ollama serves **GGUF** quantization; vLLM serves FP16 or an **AWQ/GPTQ** quant and needs
  more VRAM. Pin the closest-comparable model+quant and record it in `--notes`.
- vLLM's advantage is **concurrency**; at concurrency 1 the two are close. The story is the
  *curve*, not a single number.
- Numbers are GPU/model/quant specific — always cite the GPU and quant alongside the ratio.

## Tests
```bash
uv run pytest -q          # 16 offline tests, no GPU/network
uvx ruff check .
```
`tests/test_metrics.py` (stats + cost math), `tests/test_runner.py` (concurrency ceiling,
warmup exclusion, duration bound via virtual clock), `tests/test_report.py` (JSON round-trip,
comparison table, peak ratio).

## Results
`results/` holds committed `*.json` runs + `COMPARISON.md`. Headline figures flow into
`docs/PORTFOLIO.md` and ADR-0067 in `docs/DECISIONS.md`.
