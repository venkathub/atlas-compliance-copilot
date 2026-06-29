"""Runner tests: orchestration only, with an injected fake ``send`` (no GPU/network)."""

from __future__ import annotations

import asyncio

from atlas_bench.metrics import RequestResult
from atlas_bench.runner import run_load, run_sweep


class FakeSend:
    """Records calls + peak in-flight concurrency; yields the loop to allow overlap."""

    def __init__(self, tokens: int = 10, latency_s: float = 0.5, clock=None):
        self.calls = 0
        self.in_flight = 0
        self.peak_in_flight = 0
        self.prompts_seen: list[str] = []
        self.tokens = tokens
        self.latency_s = latency_s
        self.clock = clock  # optional VirtualClock to advance per call

    async def __call__(self, prompt: str) -> RequestResult:
        self.calls += 1
        self.prompts_seen.append(prompt)
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        await asyncio.sleep(0)  # yield so concurrent workers actually overlap
        if self.clock is not None:
            self.clock.advance(self.latency_s)
        self.in_flight -= 1
        return RequestResult(
            ok=True, latency_s=self.latency_s, ttft_s=0.1, output_tokens=self.tokens
        )


class VirtualClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_run_load_issues_exactly_total_requests():
    send = FakeSend()
    bp = asyncio.run(run_load(send, ["p"], concurrency=4, total_requests=12))
    assert send.calls == 12
    assert bp.requests == 12
    assert bp.concurrency == 4


def test_run_load_respects_concurrency_ceiling():
    send = FakeSend()
    asyncio.run(run_load(send, ["p"], concurrency=4, total_requests=40))
    # never more than `concurrency` requests in flight at once
    assert send.peak_in_flight <= 4
    # and it actually parallelized (used >1 worker)
    assert send.peak_in_flight >= 2


def test_run_load_warmup_excluded_from_results():
    send = FakeSend()
    bp = asyncio.run(run_load(send, ["p"], concurrency=2, total_requests=6, warmup=3))
    assert send.calls == 9  # 3 warmup + 6 measured
    assert bp.requests == 6  # warmup not counted in the summary


def test_run_load_round_robins_prompts():
    send = FakeSend()
    asyncio.run(run_load(send, ["a", "b"], concurrency=1, total_requests=4))
    assert send.prompts_seen == ["a", "b", "a", "b"]


def test_run_load_duration_bounded_with_virtual_clock():
    clock = VirtualClock()
    send = FakeSend(latency_s=1.0, clock=clock)
    # each call advances the clock 1s; concurrency=1 -> ~3 calls fit in a 3s window
    bp = asyncio.run(
        run_load(send, ["p"], concurrency=1, duration_s=3.0, clock=clock.now, sleep=_no_sleep)
    )
    assert send.calls == 3
    assert bp.wall_s == 3.0


def test_run_load_validates_stop_condition():
    send = FakeSend()
    # both set -> error
    try:
        asyncio.run(run_load(send, ["p"], concurrency=1, total_requests=1, duration_s=1.0))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_run_sweep_one_point_per_level_and_callback():
    seen = []
    send = FakeSend()
    points = asyncio.run(
        run_sweep(lambda: send, ["p"], [1, 2, 4], total_requests=4, on_point=seen.append)
    )
    assert [p.concurrency for p in points] == [1, 2, 4]
    assert len(seen) == 3


async def _no_sleep(_s: float) -> None:
    return None
