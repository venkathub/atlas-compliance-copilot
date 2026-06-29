"""Async load generator: drive a concurrency sweep against an injectable ``send`` coroutine.

The runner knows nothing about HTTP. It takes a ``SendFn`` — ``async (prompt) ->
RequestResult`` — so the live client (client.py) and the offline unit tests share the exact
same orchestration. ``run_load`` holds N requests in flight at one concurrency level;
``run_sweep`` walks a list of levels and returns one BenchPoint each.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence

from atlas_bench.metrics import BenchPoint, RequestResult, summarize

# Given a prompt, perform one request and return its sample.
SendFn = Callable[[str], Awaitable[RequestResult]]

# Injectable clock + sleep so duration-bounded runs are deterministic in tests.
Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


async def run_load(
    send: SendFn,
    prompts: Sequence[str],
    *,
    concurrency: int,
    total_requests: int | None = None,
    duration_s: float | None = None,
    warmup: int = 0,
    clock: Clock = time.monotonic,
    sleep: Sleep = asyncio.sleep,
) -> BenchPoint:
    """Run one concurrency level and return its summary.

    Stop condition is whichever of ``total_requests`` / ``duration_s`` is set (exactly one
    should be). ``warmup`` requests are issued and discarded before timing starts so the
    measured window excludes model load / JIT / cold-cache effects (vLLM's first batch and
    Ollama's keep-alive warm-up would otherwise skew p99).
    """
    if not prompts:
        raise ValueError("prompts must be non-empty")
    if (total_requests is None) == (duration_s is None):
        raise ValueError("set exactly one of total_requests or duration_s")

    # ── warmup (untimed) ──────────────────────────────────────────────────────
    if warmup > 0:
        await asyncio.gather(*(send(prompts[i % len(prompts)]) for i in range(warmup)))

    results: list[RequestResult] = []
    counter = {"issued": 0}
    start = clock()
    deadline = (start + duration_s) if duration_s is not None else None

    def _should_issue() -> bool:
        if total_requests is not None:
            return counter["issued"] < total_requests
        return clock() < deadline  # type: ignore[operator]

    async def worker(worker_id: int) -> None:
        while _should_issue():
            idx = counter["issued"]
            counter["issued"] += 1
            prompt = prompts[idx % len(prompts)]
            results.append(await send(prompt))

    await asyncio.gather(*(worker(w) for w in range(concurrency)))
    wall_s = clock() - start
    return summarize(concurrency, wall_s, results)


async def run_sweep(
    send_factory: Callable[[], SendFn],
    prompts: Sequence[str],
    concurrency_levels: Sequence[int],
    *,
    total_requests: int | None = None,
    duration_s: float | None = None,
    warmup: int = 0,
    settle_s: float = 0.0,
    on_point: Callable[[BenchPoint], None] | None = None,
    clock: Clock = time.monotonic,
    sleep: Sleep = asyncio.sleep,
) -> list[BenchPoint]:
    """Walk concurrency levels low→high, returning one BenchPoint per level.

    ``send_factory`` is called once per level so the client can be rebuilt fresh (new
    connection pool sized to the level). ``settle_s`` pauses between levels to let the
    server drain in-flight work, keeping levels independent.
    """
    points: list[BenchPoint] = []
    for level in concurrency_levels:
        send = send_factory()
        point = await run_load(
            send,
            prompts,
            concurrency=level,
            total_requests=total_requests,
            duration_s=duration_s,
            warmup=warmup,
            clock=clock,
            sleep=sleep,
        )
        points.append(point)
        if on_point is not None:
            on_point(point)
        if settle_s > 0:
            await sleep(settle_s)
    return points
