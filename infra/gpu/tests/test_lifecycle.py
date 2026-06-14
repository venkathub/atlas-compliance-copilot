"""Fail-safe lifecycle tests — the headline invariant: the GPU is ALWAYS paused."""

from __future__ import annotations

import pytest

from atlas_gpu.lifecycle import GpuSession, Watchdog, poll_until_ready, run_with_gpu
from atlas_gpu.providers import GpuProviderError


class FakeProvider:
    """Records resume/pause calls; returns a fixed endpoint."""

    def __init__(
        self,
        endpoint: str = "http://fake-gpu:11434",
        pause_raises: bool = False,
        resume_raises: bool = False,
    ):
        self.name = "fake"
        self._endpoint = endpoint
        self.resumes = 0
        self.pauses = 0
        self._pause_raises = pause_raises
        self._resume_raises = resume_raises

    def resume(self) -> None:
        self.resumes += 1
        if self._resume_raises:
            raise GpuProviderError("resume blew up after partial start")

    def pause(self) -> None:
        self.pauses += 1
        if self._pause_raises:
            raise GpuProviderError("boom")

    def status(self) -> str:
        return "running"

    def endpoint(self) -> str:
        return self._endpoint


def _always_healthy(_url: str) -> bool:
    return True


def test_session_pauses_on_normal_exit():
    p = FakeProvider()
    with GpuSession(p, health_check=_always_healthy) as base_url:
        assert base_url == "http://fake-gpu:11434"
    assert p.resumes == 1
    assert p.pauses == 1  # guaranteed pause


def test_session_pauses_even_when_body_raises():
    p = FakeProvider()
    with pytest.raises(ValueError):
        with GpuSession(p, health_check=_always_healthy):
            raise ValueError("work blew up")
    assert p.pauses == 1  # paused despite the exception
    # ...and the original error propagated (not swallowed)


def test_session_pause_is_idempotent():
    p = FakeProvider()
    s = GpuSession(p, health_check=_always_healthy)
    with s:
        pass
    s.pause()  # explicit second pause
    assert p.pauses == 1


def test_session_pauses_when_resume_itself_fails():
    # A resume that partially starts the instance then raises must STILL pause.
    p = FakeProvider(resume_raises=True)
    with pytest.raises(GpuProviderError):
        with GpuSession(p, health_check=_always_healthy):
            pass
    assert p.resumes == 1
    assert p.pauses == 1  # guarded resume → guaranteed pause


def test_unhealthy_gpu_times_out_but_still_pauses():
    p = FakeProvider()
    with pytest.raises(TimeoutError):
        with GpuSession(
            p,
            health_check=lambda _u: False,  # never ready
            ready_timeout_s=0.01,
            poll_interval_s=0.001,
        ):
            pass
    assert p.resumes == 1
    assert p.pauses == 1  # timeout during enter must NOT leak a running GPU


def test_pause_failure_is_loud():
    p = FakeProvider(pause_raises=True)
    with pytest.raises(GpuProviderError):
        with GpuSession(p, health_check=_always_healthy):
            pass


def test_run_with_gpu_returns_exit_code_and_pauses():
    p = FakeProvider()
    rc = run_with_gpu(p, lambda _url: 7, health_check=_always_healthy)
    assert rc == 7
    assert p.pauses == 1


def test_run_with_gpu_pauses_when_body_raises():
    p = FakeProvider()

    def boom(_url: str) -> int:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        run_with_gpu(p, boom, health_check=_always_healthy)
    assert p.pauses == 1


def test_poll_until_ready_succeeds_after_retries():
    calls = {"n": 0}

    def healthy_on_third(_url: str) -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    poll_until_ready(
        "http://x",
        healthy_on_third,
        timeout_s=10,
        interval_s=0,
        sleep=lambda _s: None,
        now=lambda: 0.0,
    )
    assert calls["n"] == 3


def test_watchdog_fires_when_expired():
    p = FakeProvider()
    t = {"v": 0.0}
    wd = Watchdog(p, idle_timeout_s=10, now=lambda: t["v"])
    assert wd.expired() is False
    t["v"] = 11.0
    assert wd.expired() is True
    assert wd.fire() is True
    assert p.pauses == 1
    assert wd.fire() is False  # no double-pause


def test_watchdog_run_cancelled_does_not_pause():
    p = FakeProvider()
    wd = Watchdog(p, idle_timeout_s=100)
    fired = wd.run(cancelled=lambda: True, sleep=lambda _s: None)
    assert fired is False
    assert p.pauses == 0
