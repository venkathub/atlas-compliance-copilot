"""GPU session lifecycle: resume -> health-poll -> discover -> run -> GUARANTEED pause.

``GpuSession`` is a context manager whose ``__exit__`` pauses the GPU in a ``finally``
no matter how the body ends (normal, exception, or KeyboardInterrupt). ``Watchdog`` is the
second net: a deadline-based pauser that force-pauses even if the parent process is killed
before it can run its ``finally``.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from atlas_gpu.providers import GpuProvider, GpuProviderError

log = logging.getLogger("atlas_gpu")

# Injection seam so tests never touch the network.
HealthCheck = Callable[[str], bool]


def http_health_check(
    base_url: str, *, timeout_s: float = 5.0, health_path: str = "/api/tags"
) -> bool:
    """Return True iff Ollama answers on ``{base_url}{health_path}`` (models loaded).

    ``/api/tags`` is the canonical readiness probe used throughout the RUNBOOK.
    """
    url = base_url.rstrip("/") + health_path
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


def poll_until_ready(
    endpoint: str,
    health_check: HealthCheck,
    *,
    timeout_s: float = 600.0,
    interval_s: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> None:
    """Block until ``health_check(endpoint)`` is True or ``timeout_s`` elapses.

    Raises ``TimeoutError`` on timeout. Callers run this *inside* a GpuSession so a
    timeout still pauses the GPU.
    """
    deadline = now() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        if health_check(endpoint):
            log.info("GPU healthy after %d probe(s)", attempt)
            return
        if now() >= deadline:
            raise TimeoutError(
                f"GPU not healthy at {endpoint} after {timeout_s:.0f}s ({attempt} probes)"
            )
        sleep(interval_s)


class GpuSession:
    """Resume + discover the GPU on enter; **always pause on exit**.

    Usage::

        with GpuSession(provider) as base_url:
            ... do work against base_url ...
        # provider.pause() has run, even if the block raised.
    """

    def __init__(
        self,
        provider: GpuProvider,
        *,
        health_check: HealthCheck | None = None,
        ready_timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
        skip_health: bool = False,
    ) -> None:
        self.provider = provider
        self.health_check = health_check or http_health_check
        self.ready_timeout_s = ready_timeout_s
        self.poll_interval_s = poll_interval_s
        self.skip_health = skip_health
        self.base_url: str | None = None
        self._paused = False

    def __enter__(self) -> str:
        log.info("resuming GPU via provider '%s'", self.provider.name)
        try:
            # resume() is INSIDE the guard: a resume that partially starts the instance
            # then fails (e.g. wait-for-Running timeout) must still trigger a pause.
            self.provider.resume()
            endpoint = self.provider.endpoint()
            if not self.skip_health:
                poll_until_ready(
                    endpoint,
                    self.health_check,
                    timeout_s=self.ready_timeout_s,
                    interval_s=self.poll_interval_s,
                )
        except BaseException:
            # __exit__ does NOT run if __enter__ raises — so a failed resume/health-poll
            # would leak a running GPU. Pause here (defensively) before re-raising the
            # ORIGINAL error so the cause is never masked by a pause failure.
            try:
                self.pause()
            except Exception:
                log.exception("pause during failed enter ALSO failed — check the console!")
            raise
        self.base_url = endpoint
        return endpoint

    def pause(self) -> None:
        """Pause once; safe to call multiple times (idempotent guard)."""
        if self._paused:
            return
        try:
            self.provider.pause()
            self._paused = True
            log.info("GPU paused via provider '%s'", self.provider.name)
        except GpuProviderError:
            # A pause failure must scream, not pass silently — cost is at stake.
            log.exception("GPU PAUSE FAILED — verify the instance is stopped in the console!")
            raise

    def __exit__(self, exc_type, exc, tb) -> bool:
        # finally-semantics: pause regardless of how the body ended; never swallow exc.
        self.pause()
        return False


def run_with_gpu(
    provider: GpuProvider,
    body: Callable[[str], int],
    *,
    health_check: HealthCheck | None = None,
    ready_timeout_s: float = 600.0,
    skip_health: bool = False,
) -> int:
    """Resume the GPU, run ``body(base_url)``, and guarantee a pause afterwards.

    Returns ``body``'s int exit code. The pause runs even if ``body`` raises.
    """
    with GpuSession(
        provider,
        health_check=health_check,
        ready_timeout_s=ready_timeout_s,
        skip_health=skip_health,
    ) as base_url:
        return int(body(base_url))


class Watchdog:
    """Deadline-based fail-safe: pause the GPU once ``idle_timeout_s`` has elapsed.

    Used by the ``up``/``down`` split (interactive sessions) where no single long-lived
    process owns a ``finally``. ``expired(now)`` is a pure function so the deadline logic
    is unit-tested without sleeping; the CLI runs the detached loop.
    """

    def __init__(
        self,
        provider: GpuProvider,
        idle_timeout_s: float,
        *,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider = provider
        self.idle_timeout_s = idle_timeout_s
        self._now = now
        self.deadline = now() + idle_timeout_s
        self._fired = False

    def expired(self, at: float | None = None) -> bool:
        return (self._now() if at is None else at) >= self.deadline

    def fire(self) -> bool:
        """Pause the GPU if not already fired. Returns True if it paused this call."""
        if self._fired:
            return False
        self.provider.pause()
        self._fired = True
        log.warning("watchdog fired: idle timeout reached, GPU paused")
        return True

    def run(
        self,
        *,
        cancelled: Callable[[], bool],
        sleep: Callable[[float], None] = time.sleep,
        tick_s: float = 5.0,
    ) -> bool:
        """Loop until expired or ``cancelled()``. Pauses on expiry; no-op if cancelled."""
        while not cancelled():
            if self.expired():
                return self.fire()
            sleep(tick_s)
        log.info("watchdog cancelled (session ended cleanly)")
        return False
