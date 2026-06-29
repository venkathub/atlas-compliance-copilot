"""JarvisLabs GPU provider, backed by the official ``jarvislabs`` SDK (via the JlClient seam).

Replaces the previous raw-urllib driver (ADR-0066). Implements the ``GpuProvider`` Protocol
(``resume``/``pause``/``status``/``endpoint``) so ``lifecycle.py`` and the fail-safe watchdog
are unchanged, and adds ``create()`` / ``destroy()`` for from-scratch provisioning.

Endpoint discovery does not assume port→URL order: it **probes** the instance's public
endpoints to find the Ollama/vLLM URL (see ``provision.classify_endpoints``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from atlas_gpu.provision import (
    EndpointProbe,
    ProvisionConfig,
    build_startup_script,
    classify_endpoints,
    http_probe,
)
from atlas_gpu.sdk import InstanceInfo, JlClient, JlError, make_client

log = logging.getLogger("atlas_gpu")

# Re-exported for back-compat with existing imports/tests.
GpuProviderError = JlError


@runtime_checkable
class GpuProvider(Protocol):
    """Minimal lifecycle contract consumed by ``lifecycle.py`` / the watchdog."""

    name: str

    def resume(self) -> None: ...
    def pause(self) -> None: ...
    def status(self) -> str: ...
    def endpoint(self) -> str: ...


@dataclass
class CreateSpec:
    """Parameters for creating a fresh instance (defaulted from env)."""

    gpu_type: str = "A100"
    num_gpus: int = 1
    template: str = "pytorch"
    storage_gb: int = 100
    name: str = "atlas-serving"
    region: str | None = None

    @classmethod
    def from_env(cls, env: dict | None = None) -> CreateSpec:
        env = os.environ if env is None else env
        return cls(
            gpu_type=env.get("GPU_TYPE", cls.gpu_type),
            num_gpus=int(env.get("GPU_NUM_GPUS", cls.num_gpus)),
            template=env.get("GPU_TEMPLATE", cls.template),
            storage_gb=int(env.get("GPU_STORAGE_GB", cls.storage_gb)),
            name=env.get("GPU_INSTANCE_NAME", cls.name),
            region=env.get("GPU_REGION") or None,
        )


@dataclass
class JarvisLabsProvider:
    """Drive a JarvisLabs instance through the SDK seam."""

    name: str
    client: JlClient
    instance_id: str = ""
    create_spec: CreateSpec = field(default_factory=CreateSpec)
    probe: EndpointProbe = http_probe
    _roles: dict[str, str] = field(default_factory=dict, repr=False)

    # ── lifecycle (GpuProvider Protocol) ──────────────────────────────────────
    def status(self) -> str:
        return self.client.get_instance(self.instance_id).status

    def resume(self) -> None:
        """Resume the paused instance and block until Running (machine_id may change)."""
        if not self.instance_id:
            raise JlError("resume requires GPU_INSTANCE_ID (or create one first)")
        info = self.client.get_instance(self.instance_id)
        if info.is_running:
            self._roles = {}
            return
        info = self.client.resume_instance(self.instance_id)
        self.instance_id = info.machine_id  # CRITICAL: id can change on resume
        self._roles = {}

    def pause(self) -> None:
        if not self.instance_id:
            raise JlError("pause requires an instance id")
        self.client.pause_instance(self.instance_id)

    def destroy(self) -> None:
        if not self.instance_id:
            raise JlError("destroy requires an instance id")
        self.client.destroy_instance(self.instance_id)

    def endpoint(self) -> str:
        """Return the primary OpenAI-compatible base URL (Ollama preferred, else vLLM)."""
        roles = self.discover_endpoints()
        url = roles.get("ollama") or roles.get("vllm")
        if not url:
            raise JlError(f"instance {self.instance_id} exposes no ready endpoint")
        return url

    def discover_endpoints(self, *, refresh: bool = False) -> dict[str, str]:
        """Probe the instance's public endpoints → ``{"ollama": url, "vllm": url}``."""
        if self._roles and not refresh:
            return self._roles
        info = self.client.get_instance(self.instance_id)
        self._roles = classify_endpoints(info.endpoints, self.probe)
        return self._roles

    # ── from-scratch creation ─────────────────────────────────────────────────
    def create(self, config: ProvisionConfig) -> InstanceInfo:
        """Create a fresh instance with a startup script that serves ``config.target``."""
        script = build_startup_script(config)
        script_id = self.client.add_script(
            script=script, name=f"atlas-provision-{config.target.value}"
        )
        info = self.client.create_instance(
            gpu_type=self.create_spec.gpu_type,
            num_gpus=self.create_spec.num_gpus,
            template=self.create_spec.template,
            storage=self.create_spec.storage_gb,
            name=self.create_spec.name,
            http_ports=config.http_ports(),
            script_id=script_id,
            region=self.create_spec.region,
        )
        self.instance_id = info.machine_id
        self._roles = {}
        log.info("created instance %s (%s)", info.machine_id, self.create_spec.gpu_type)
        return info


def make_provider(name: str | None = None, *, env: dict | None = None) -> JarvisLabsProvider:
    """Build a JarvisLabs provider from ``GPU_*`` env vars.

    ``GPU_PROVIDER`` is accepted for forward-compat but only ``jarvislabs`` is supported now
    (the generic E2E seam was removed with the SDK migration — ADR-0066). An unknown value
    fails loudly so a typo never silently skips a pause.
    """
    env = os.environ if env is None else env
    name = (name or env.get("GPU_PROVIDER") or "jarvislabs").strip().lower()
    if name != "jarvislabs":
        raise JlError(f"unsupported GPU_PROVIDER '{name}' (only 'jarvislabs' is supported)")
    return JarvisLabsProvider(
        name=name,
        client=make_client(env),
        instance_id=env.get("GPU_INSTANCE_ID", ""),
        create_spec=CreateSpec.from_env(env),
    )
