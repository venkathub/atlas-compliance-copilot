"""Offline, GPU-free tests for per-run training-cost capture (P6 Task 9).

Covers the ₹/hr × wall-clock math, env rate parsing, CostRecord round-trip, and the key
finally-semantics: the window is timed (and cost recorded) even when the body raises.
"""

from __future__ import annotations

import pytest

from atlas_training.cost import (
    CostError,
    CostMeter,
    CostRecord,
    compute_cost,
    costed_gpu_window,
    gpu_rate_from_env,
)

# ── cost math ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rate,wall,expected",
    [
        (50.0, 3600.0, 50.0),      # one hour
        (50.0, 1800.0, 25.0),      # half hour
        (1000.0, 86400.0, 24000.0),  # ~1 L4-day sanity (rate is illustrative)
        (0.0, 3600.0, 0.0),
        (50.0, 0.0, 0.0),
    ],
)
def test_compute_cost(rate, wall, expected):
    assert compute_cost(rate, wall) == pytest.approx(expected)


def test_compute_cost_rejects_negative():
    with pytest.raises(CostError):
        compute_cost(-1.0, 10.0)
    with pytest.raises(CostError):
        compute_cost(1.0, -10.0)


# ── env rate ───────────────────────────────────────────────────────────────────────────────────


def test_gpu_rate_from_env():
    rate, currency = gpu_rate_from_env({"ATLAS_GPU_COST_PER_HOUR": "42.5"})
    assert rate == 42.5 and currency == "INR"
    rate, currency = gpu_rate_from_env(
        {"ATLAS_GPU_COST_PER_HOUR": "30", "ATLAS_GPU_COST_CURRENCY": "USD"}
    )
    assert rate == 30.0 and currency == "USD"


@pytest.mark.parametrize("env", [{}, {"ATLAS_GPU_COST_PER_HOUR": ""}])
def test_gpu_rate_unset_raises(env):
    with pytest.raises(CostError, match="ATLAS_GPU_COST_PER_HOUR"):
        gpu_rate_from_env(env)


def test_gpu_rate_non_numeric_raises():
    with pytest.raises(CostError, match="not a number"):
        gpu_rate_from_env({"ATLAS_GPU_COST_PER_HOUR": "cheap"})


# ── CostMeter + record ───────────────────────────────────────────────────────────────────────────


def test_meter_measures_window():
    ticks = iter([100.0, 1900.0])  # enter-start, exit-end (wall_clock datetimes are separate)
    m = CostMeter(now=lambda: next(ticks))
    with m:
        pass
    assert m.wall_seconds == pytest.approx(1800.0)
    rec = m.record(50.0)
    assert isinstance(rec, CostRecord)
    assert rec.cost == pytest.approx(25.0)
    assert rec.wall_seconds == pytest.approx(1800.0)
    assert rec.teardown_recorded is True
    assert rec.started_at and rec.ended_at


def test_meter_records_cost_even_when_body_raises():
    # The "teardown always recorded" property: a failed training run still yields a cost record.
    ticks = iter([0.0, 3600.0])
    m = CostMeter(now=lambda: next(ticks))
    with pytest.raises(RuntimeError):
        with m:
            raise RuntimeError("training blew up")
    rec = m.record(100.0, teardown_recorded=True)
    assert rec.wall_seconds == pytest.approx(3600.0)
    assert rec.cost == pytest.approx(100.0)


def test_meter_record_before_enter_raises():
    with pytest.raises(CostError, match="never entered"):
        _ = CostMeter().wall_seconds


def test_record_round_trip(tmp_path):
    m = CostMeter(now=iter([0.0, 60.0]).__next__)
    with m:
        pass
    rec = m.record(60.0)
    p = tmp_path / "cost.json"
    rec.save(p)
    import json

    loaded = CostRecord.from_dict(json.loads(p.read_text()))
    assert loaded == rec


# ── costed_gpu_window (duck-typed session) ─────────────────────────────────────────────────────


class FakeSession:
    """A GpuSession-like context manager that records pause-on-exit."""

    def __init__(self):
        self.paused = False

    def __enter__(self):
        return "http://gpu:11434"

    def __exit__(self, *exc):
        self.paused = True  # guaranteed teardown, mirrors GpuSession
        return False


def test_costed_gpu_window_runs_body_and_records():
    session = FakeSession()
    ticks = iter([0.0, 7200.0])
    result, rec = costed_gpu_window(
        session, lambda url: f"trained@{url}", rate_per_hour=50.0,
        now=lambda: next(ticks),
    )
    assert result == "trained@http://gpu:11434"
    assert session.paused is True  # teardown happened
    assert rec.teardown_recorded is True
    assert rec.cost == pytest.approx(100.0)  # 2h × 50
