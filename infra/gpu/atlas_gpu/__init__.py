"""Atlas GPU lifecycle + from-scratch provisioner (infra/gpu).

Two capabilities behind one tool (ADR-0029 lifecycle, ADR-0066 SDK migration + provisioner):

  - **Lifecycle** — resume an existing GPU, health-poll, discover the serving endpoint,
    run work, then **GUARANTEE a pause** (``finally``/trap) plus an idle-timeout watchdog.
  - **From-scratch provisioning** — create a GPU instance via the official ``jarvislabs``
    SDK, install/serve Ollama and/or vLLM (OpenAI-compatible), discover + write the
    endpoint env vars, and leave it running under the watchdog.

The cardinal invariant is unchanged: *automation that can start the GPU must never be able
to leave it running.* Every entry point pauses in a ``finally`` and the watchdog pauses on
deadline even if the parent is killed.
"""

from atlas_gpu.bootstrap import ProvisionResult, provision_from_scratch
from atlas_gpu.lifecycle import GpuSession, Watchdog, run_with_gpu
from atlas_gpu.providers import GpuProvider, JarvisLabsProvider, make_provider
from atlas_gpu.provision import ProvisionConfig, ServeTarget

__all__ = [
    "GpuSession",
    "Watchdog",
    "run_with_gpu",
    "GpuProvider",
    "JarvisLabsProvider",
    "make_provider",
    "ProvisionConfig",
    "ServeTarget",
    "ProvisionResult",
    "provision_from_scratch",
]
