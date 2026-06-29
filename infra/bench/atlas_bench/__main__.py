"""CLI: run a concurrency sweep against a live OpenAI-compatible endpoint.

Examples (GPU on):
  # Benchmark the current Ollama endpoint
  uv run python -m atlas_bench run \\
      --backend ollama --base-url "$OLLAMA_BASE_URL" --model qwen2.5:7b-instruct \\
      --gpu "L4" --gpu-cost-per-hour 41 \\
      --concurrency 1,4,8,16,32 --requests-per-level 60 --warmup 4 \\
      --out results/ollama-L4.json

  # Benchmark vLLM serving the same model family on the same GPU, then compare
  uv run python -m atlas_bench run --backend vllm --base-url http://gpu:8000 ... \\
      --out results/vllm-L4.json
  uv run python -m atlas_bench compare results/ollama-L4.json results/vllm-L4.json \\
      --out results/COMPARISON.md

The `run` subcommand needs a GPU/endpoint; `compare` is pure offline post-processing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from atlas_bench.metrics import BenchPoint
from atlas_bench.report import BenchRun, compare_markdown


def _levels(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip()]


def _load_prompts(path: str | None) -> list[str]:
    from atlas_bench.client import DEFAULT_PROMPTS

    if not path:
        return list(DEFAULT_PROMPTS)
    return [ln for ln in Path(path).read_text().splitlines() if ln.strip()]


def cmd_run(args: argparse.Namespace) -> int:
    # Imported lazily so `compare` (and unit tests) never require httpx.
    from atlas_bench.client import ChatClientConfig, make_send
    from atlas_bench.runner import run_sweep

    prompts = _load_prompts(args.prompts)
    levels = _levels(args.concurrency)
    cfg = ChatClientConfig(
        base_url=args.base_url, model=args.model, max_tokens=args.max_tokens,
        timeout_s=args.timeout,
    )

    clients = []

    def factory_for(level: int):
        send, client = make_send(cfg, max_connections=level)
        clients.append(client)
        return send

    async def go() -> list[BenchPoint]:
        # run_sweep calls send_factory() once per level; we close clients after.
        level_iter = iter(levels)

        def send_factory():
            return factory_for(next(level_iter))

        try:
            return await run_sweep(
                send_factory, prompts, levels,
                total_requests=args.requests_per_level, warmup=args.warmup,
                settle_s=args.settle,
                on_point=lambda p: print(
                    f"[bench] c={p.concurrency:>3} "
                    f"tok/s={p.output_tokens_per_s:>8.1f} "
                    f"req/s={p.requests_per_s:>6.2f} "
                    f"ttft_p50={p.ttft_p50_ms:>6.0f}ms "
                    f"e2e_p99={p.e2e_p99_ms:>7.0f}ms "
                    f"err={p.error_rate:.1%}",
                    file=sys.stderr,
                ),
            )
        finally:
            for c in clients:
                await c.aclose()

    points = asyncio.run(go())
    run = BenchRun(
        backend=args.backend, model=args.model, gpu=args.gpu,
        gpu_cost_per_hour=args.gpu_cost_per_hour, points=points,
        token_accounting=args.token_accounting, notes=args.notes,
        meta={"max_tokens": args.max_tokens, "requests_per_level": args.requests_per_level,
              "warmup": args.warmup, "prompts": len(prompts)},
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    run.write_json(args.out)
    print(f"[bench] wrote {args.out}", file=sys.stderr)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    runs = []
    for path in args.results:
        data = json.loads(Path(path).read_text())
        points = [BenchPoint(**p) for p in data["points"]]
        runs.append(BenchRun(
            backend=data["backend"], model=data["model"], gpu=data["gpu"],
            gpu_cost_per_hour=data.get("gpu_cost_per_hour", 0.0), points=points,
            token_accounting=data.get("token_accounting", "server-reported"),
            notes=data.get("notes", ""),
        ))
    md = compare_markdown(runs)
    if args.out:
        Path(args.out).write_text(md)
        print(f"[bench] wrote {args.out}", file=sys.stderr)
    else:
        print(md)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atlas_bench", description="Atlas serving benchmark")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a concurrency sweep against a live endpoint")
    r.add_argument("--backend", required=True, choices=["ollama", "vllm"])
    r.add_argument("--base-url", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--gpu", default="unknown", help="GPU label, e.g. L4 / A5000")
    r.add_argument("--gpu-cost-per-hour", type=float, default=0.0)
    r.add_argument("--concurrency", default="1,4,8,16,32", help="comma-separated levels")
    r.add_argument("--requests-per-level", type=int, default=60)
    r.add_argument("--warmup", type=int, default=4)
    r.add_argument("--settle", type=float, default=2.0, help="pause between levels (s)")
    r.add_argument("--max-tokens", type=int, default=256)
    r.add_argument("--timeout", type=float, default=120.0)
    r.add_argument("--prompts", help="file with one prompt per line (default: built-in set)")
    r.add_argument("--token-accounting", default="server-reported",
                   choices=["server-reported", "proxy"])
    r.add_argument("--notes", default="", help="quantization / model caveats for the report")
    r.add_argument("--out", required=True, help="output JSON path")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("compare", help="render a Markdown comparison from result JSONs")
    c.add_argument("results", nargs="+", help="benchmark result JSON files")
    c.add_argument("--out", help="output .md path (default: stdout)")
    c.set_defaults(func=cmd_compare)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
