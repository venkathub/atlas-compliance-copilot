"""Thin seam over the official ``jarvislabs`` SDK (the only place that imports it).

Why a seam instead of using ``jarvislabs.Client`` directly in the provider:
  - **Lazy import.** The SDK is imported *inside* ``RealJlClient`` methods, so importing
    ``atlas_gpu`` (and the guaranteed-pause watchdog path) never requires the package.
  - **Offline tests.** ``providers.py`` depends on the ``JlClient`` Protocol, so unit tests
    inject a ``FakeJlClient`` and run with no SDK install and no network.
  - **Normalisation.** SDK ``Instance`` objects (pydantic) are flattened into a stable
    ``InstanceInfo`` dataclass exposing only the fields Atlas uses, insulating us from SDK
    field churn.

Auth: the token is read from ``GPU_API_KEY`` (existing Atlas convention) and passed as
``Client(api_key=...)`` — we do NOT rely on ``jl setup`` / ``JL_API_KEY``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class JlError(RuntimeError):
    """Raised when an SDK call fails (never contains the API key)."""


@dataclass
class InstanceInfo:
    """Flattened view of a JarvisLabs instance — only the fields Atlas needs."""

    machine_id: str
    status: str
    endpoints: list[str] = field(default_factory=list)
    url: str | None = None
    http_ports: str | None = None
    region: str | None = None

    @property
    def is_running(self) -> bool:
        return str(self.status).lower() == "running"


def _to_info(inst: object) -> InstanceInfo:
    """Convert an SDK ``Instance`` (or a dict) into ``InstanceInfo`` defensively."""

    def g(name: str, default=None):
        if isinstance(inst, dict):
            return inst.get(name, default)
        return getattr(inst, name, default)

    eps = g("endpoints") or []
    if isinstance(eps, str):
        eps = [eps]
    return InstanceInfo(
        machine_id=str(g("machine_id", "")),
        status=str(g("status", "unknown")),
        endpoints=[str(e) for e in eps],
        url=(str(g("url")) if g("url") else None),
        http_ports=(str(g("http_ports")) if g("http_ports") else None),
        region=(str(g("region")) if g("region") else None),
    )


@runtime_checkable
class JlClient(Protocol):
    """Minimal contract over the JarvisLabs SDK that ``JarvisLabsProvider`` relies on."""

    def create_instance(
        self,
        *,
        gpu_type: str,
        num_gpus: int,
        template: str,
        storage: int,
        name: str,
        http_ports: str,
        script_id: str | None,
        region: str | None,
    ) -> InstanceInfo:
        """Create an instance and block until Running. Returns its InstanceInfo."""

    def get_instance(self, machine_id: str) -> InstanceInfo: ...

    def list_instances(self) -> list[InstanceInfo]: ...

    def resume_instance(self, machine_id: str) -> InstanceInfo:
        """Resume a paused instance and block until Running (machine_id may change)."""

    def pause_instance(self, machine_id: str) -> None: ...

    def destroy_instance(self, machine_id: str) -> None: ...

    def add_script(self, *, script: str, name: str) -> str:
        """Upload a startup script; return its id (as a string, ready for create)."""


@dataclass
class RealJlClient:
    """Adapter around ``jarvislabs.Client`` (lazy-imported, key never logged)."""

    api_key: str
    _client: object = field(default=None, repr=False)

    def _c(self):
        if self._client is None:
            try:
                from jarvislabs import Client  # lazy: only needed for live calls
            except ImportError as e:  # pragma: no cover - env-dependent
                raise JlError(
                    "the 'jarvislabs' package is required for live GPU calls; "
                    "install it (uv sync / pip install jarvislabs)"
                ) from e
            self._client = Client(api_key=self.api_key or None)
        return self._client

    def _wrap(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except JlError:
            raise
        except Exception as e:  # normalise SDK errors; keep the type name, drop internals
            raise JlError(f"jarvislabs call failed: {type(e).__name__}") from None

    def create_instance(self, **kw) -> InstanceInfo:
        return _to_info(self._wrap(self._c().instances.create, **kw))

    def get_instance(self, machine_id: str) -> InstanceInfo:
        return _to_info(self._wrap(self._c().instances.get, int(machine_id)))

    def list_instances(self) -> list[InstanceInfo]:
        return [_to_info(i) for i in self._wrap(self._c().instances.list)]

    def resume_instance(self, machine_id: str) -> InstanceInfo:
        return _to_info(self._wrap(self._c().instances.resume, int(machine_id)))

    def pause_instance(self, machine_id: str) -> None:
        self._wrap(self._c().instances.pause, int(machine_id))

    def destroy_instance(self, machine_id: str) -> None:
        self._wrap(self._c().instances.destroy, int(machine_id))

    def add_script(self, *, script: str, name: str) -> str:
        # Upsert by name: reuse/refresh an existing script rather than piling up new ones.
        # JarvisLabs caps stored startup scripts — repeated provisions otherwise eventually
        # fail at scripts.add with APIError (found live 2026-06-29, ADR-0066).
        for s in self._wrap(self._c().scripts.list):
            if getattr(s, "script_name", None) == name:
                sid = str(s.script_id)
                self._wrap(self._c().scripts.update, int(sid), script)
                return sid
        self._wrap(self._c().scripts.add, script=script, name=name)
        for s in self._wrap(self._c().scripts.list):
            if getattr(s, "script_name", None) == name:
                return str(s.script_id)
        raise JlError(f"uploaded script '{name}' but could not resolve its id")


def make_client(env: dict | None = None) -> JlClient:
    """Build a live ``JlClient`` from ``GPU_API_KEY`` (Atlas convention)."""
    env = os.environ if env is None else env
    return RealJlClient(api_key=env.get("GPU_API_KEY", ""))
