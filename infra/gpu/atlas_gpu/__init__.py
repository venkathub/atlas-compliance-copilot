"""Atlas fail-safe GPU lifecycle helper (infra/gpu).

Resume the Cloud Ollama GPU, health-poll it, discover the fresh ``OLLAMA_BASE_URL``,
run work against it, then **GUARANTEE a pause** (``finally``/trap) plus an idle-timeout
watchdog as a second net. See ADR-0029 (D-P2-9) and RUNBOOK §2.4 / §6.

The cardinal invariant: *automation that can resume the GPU must never be able to leave
it running.* Every public entry point pauses in a ``finally`` and the watchdog pauses on
deadline even if the parent process is killed.
"""

from atlas_gpu.lifecycle import GpuSession, Watchdog, run_with_gpu
from atlas_gpu.providers import GpuProvider, make_provider

__all__ = [
    "GpuSession",
    "Watchdog",
    "run_with_gpu",
    "GpuProvider",
    "make_provider",
]
