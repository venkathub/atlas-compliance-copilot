"""Per-run training-cost capture (GPU ₹/hr × wall-clock) — GPU-free, env-driven.

The episodic training window runs on a paid GPU (JarvisLabs L4). This module turns the window's
wall-clock and the env-configured GPU rate into a committed `CostRecord` (part of the Task 11
evidence). It composes with `infra/gpu`'s `GpuSession` — whose guaranteed-pause teardown is already
tested (ADR-0066) — via a duck-typed seam, so it adds NO dependency and stays unit-testable with no
GPU. The rate is never hardcoded (CLAUDE.md cost discipline) — it comes from
`ATLAS_GPU_COST_PER_HOUR`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CURRENCY = "INR"


class CostError(ValueError):
    """Raised when the GPU rate is unconfigured/invalid or a cost window is misused."""


def gpu_rate_from_env(env: dict[str, str] | None = None) -> tuple[float, str]:
    """Read (rate_per_hour, currency) from the environment. Raises if the rate is unset/invalid.

    No default rate is baked in — the GPU price is a deployment fact, configured via
    `ATLAS_GPU_COST_PER_HOUR` (+ optional `ATLAS_GPU_COST_CURRENCY`, default INR).
    """
    import os

    env = os.environ if env is None else env
    raw = env.get("ATLAS_GPU_COST_PER_HOUR")
    if raw is None or str(raw).strip() == "":
        raise CostError("ATLAS_GPU_COST_PER_HOUR is unset — configure the GPU ₹/hr rate")
    try:
        rate = float(raw)
    except ValueError as exc:
        raise CostError(f"ATLAS_GPU_COST_PER_HOUR is not a number: {raw!r}") from exc
    if rate < 0:
        raise CostError(f"ATLAS_GPU_COST_PER_HOUR must be non-negative, got {rate}")
    return rate, env.get("ATLAS_GPU_COST_CURRENCY", DEFAULT_CURRENCY)


def compute_cost(rate_per_hour: float, wall_seconds: float) -> float:
    """Cost of a window = rate_per_hour × hours. Rounded to 4 dp."""
    if rate_per_hour < 0 or wall_seconds < 0:
        raise CostError("rate_per_hour and wall_seconds must be non-negative")
    return round(rate_per_hour * (wall_seconds / 3600.0), 4)


@dataclass(frozen=True)
class CostRecord:
    rate_per_hour: float
    currency: str
    wall_seconds: float
    cost: float
    teardown_recorded: bool
    started_at: str
    ended_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CostRecord:
        return cls(**raw)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


class CostMeter:
    """Times a (GPU) window. `__exit__` stops the clock in a finally, so the window is always
    measurable — cost is recorded even if the body raised. `record()` builds the CostRecord.
    """

    def __init__(
        self,
        *,
        now: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._now = now
        self._wall_clock = wall_clock
        self._start: float | None = None
        self._end: float | None = None
        self._started_at: str | None = None
        self._ended_at: str | None = None

    def __enter__(self) -> CostMeter:
        self._start = self._now()
        self._started_at = self._wall_clock().isoformat()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # finally-semantics: stop the clock however the body ended; never swallow the exception.
        if self._end is None:
            self._end = self._now()
            self._ended_at = self._wall_clock().isoformat()
        return False

    @property
    def wall_seconds(self) -> float:
        if self._start is None:
            raise CostError("CostMeter was never entered")
        end = self._end if self._end is not None else self._now()
        return max(0.0, end - self._start)

    def record(
        self, rate_per_hour: float, *, currency: str = DEFAULT_CURRENCY,
        teardown_recorded: bool = True,
    ) -> CostRecord:
        wall = self.wall_seconds
        return CostRecord(
            rate_per_hour=rate_per_hour,
            currency=currency,
            wall_seconds=round(wall, 3),
            cost=compute_cost(rate_per_hour, wall),
            teardown_recorded=teardown_recorded,
            started_at=self._started_at or "",
            ended_at=self._ended_at or self._wall_clock().isoformat(),
        )


def costed_gpu_window(  # pragma: no cover - composed in the episodic GPU window (Task 11)
    session,
    body: Callable[[str], Any],
    *,
    rate_per_hour: float,
    currency: str = DEFAULT_CURRENCY,
    now: Callable[[], float] = time.monotonic,
) -> tuple[Any, CostRecord]:
    """Run `body(base_url)` inside `session` (a GpuSession-like CM, guaranteed pause on exit) while
    timing the window. Returns (result, CostRecord). `session` is duck-typed — no atlas_gpu import.
    """
    meter = CostMeter(now=now)
    with meter:
        with session as base_url:  # GpuSession.__exit__ guarantees the pause (ADR-0066)
            result = body(base_url)
    return result, meter.record(rate_per_hour, currency=currency, teardown_recorded=True)
