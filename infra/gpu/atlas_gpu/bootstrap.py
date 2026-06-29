"""End-to-end, from-scratch GPU provisioning orchestration (Task 0).

``provision_from_scratch`` ties the pieces together:

    build startup script -> create instance (blocks until Running) ->
    health-poll the OpenAI-compatible endpoint(s) until the script finishes
    installing/pulling -> classify endpoints -> write OLLAMA_BASE_URL /
    ATLAS_VLLM_BASE_URL / GPU_INSTANCE_ID -> return the URLs.

It never destroys anything; the caller arms the fail-safe watchdog (CLI ``provision``) and
later tears down with ``pause`` (default) or ``--destroy``. A ``dry_run`` mode prints the
plan + the exact startup script without touching the account.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from atlas_gpu.providers import JarvisLabsProvider
from atlas_gpu.provision import ProvisionConfig, ServeTarget, build_startup_script
from atlas_gpu.sdk import JlError

log = logging.getLogger("atlas_gpu")


@dataclass
class ProvisionResult:
    machine_id: str
    ollama_base_url: str | None = None
    vllm_base_url: str | None = None
    dry_run: bool = False
    script: str = field(default="", repr=False)


def write_env(path: str, key: str, value: str) -> None:
    """Update (or append) ``KEY=value`` in an env file, preserving other lines."""
    p = Path(path)
    lines = p.read_text().splitlines() if p.exists() else []
    out, found = [], False
    for line in lines:
        if line.startswith(f"{key}=") and not line.lstrip().startswith("#"):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    p.write_text("\n".join(out) + "\n")


def _desired_roles(target: ServeTarget) -> set[str]:
    roles: set[str] = set()
    if target.wants_ollama:
        roles.add("ollama")
    if target.wants_vllm:
        roles.add("vllm")
    return roles


def wait_for_roles(
    provider: JarvisLabsProvider,
    target: ServeTarget,
    *,
    ready_timeout_s: float = 1800.0,
    poll_interval_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, str]:
    """Poll until every desired role responds on its endpoint, or time out.

    The timeout defaults high (30 min): a fresh instance has to install the server and pull
    a model (Ollama) or load weights (vLLM), all of which run in the startup script after
    the instance is already ``Running``.
    """
    desired = _desired_roles(target)
    deadline = now() + ready_timeout_s
    attempt = 0
    while True:
        attempt += 1
        roles = provider.discover_endpoints(refresh=True)
        if desired.issubset(roles.keys()):
            log.info("all serve targets ready after %d probe(s): %s", attempt, sorted(desired))
            return roles
        if now() >= deadline:
            raise TimeoutError(
                f"serve targets {sorted(desired - set(roles))} not ready after "
                f"{ready_timeout_s:.0f}s (got {sorted(roles)})"
            )
        sleep(poll_interval_s)


def provision_from_scratch(
    provider: JarvisLabsProvider,
    config: ProvisionConfig,
    *,
    env_file: str | None = None,
    ready_timeout_s: float = 1800.0,
    poll_interval_s: float = 10.0,
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> ProvisionResult:
    """Create + provision a GPU instance from nothing and return the serving URLs."""
    script = build_startup_script(config)

    if config.target == ServeTarget.BOTH:
        log.warning(
            "serve target 'both' runs Ollama + vLLM on ONE GPU — they share VRAM; "
            "prefer a larger GPU (e.g. A100) or run them in separate sessions."
        )

    if dry_run:
        log.info(
            "[dry-run] would create %s GPU, storage=%dGB, ports=%s, target=%s",
            provider.create_spec.gpu_type,
            provider.create_spec.storage_gb,
            config.http_ports(),
            config.target.value,
        )
        return ProvisionResult(machine_id="(dry-run)", dry_run=True, script=script)

    info = provider.create(config)
    log.info("instance %s is Running; waiting for serve targets to come up", info.machine_id)

    roles = wait_for_roles(
        provider,
        config.target,
        ready_timeout_s=ready_timeout_s,
        poll_interval_s=poll_interval_s,
        sleep=sleep,
        now=now,
    )
    ollama = roles.get("ollama")
    vllm = roles.get("vllm")

    if env_file:
        if ollama:
            write_env(env_file, "OLLAMA_BASE_URL", ollama)
        if vllm:
            write_env(env_file, "ATLAS_VLLM_BASE_URL", vllm)
        write_env(env_file, "GPU_INSTANCE_ID", provider.instance_id)
        log.info("wrote endpoint(s) + GPU_INSTANCE_ID to %s", env_file)

    if not ollama and not vllm:  # defensive — wait_for_roles should have raised
        raise JlError("provisioning produced no usable endpoint")

    return ProvisionResult(
        machine_id=provider.instance_id,
        ollama_base_url=ollama,
        vllm_base_url=vllm,
        script=script,
    )
