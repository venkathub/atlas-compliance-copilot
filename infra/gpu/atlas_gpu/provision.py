"""From-scratch provisioning: what to serve, the startup script, and endpoint discovery.

This module is pure (no SDK, no live network except the injectable ``probe``) so it is
fully unit-testable offline:
  - ``ServeTarget`` — ollama, vllm, or both.
  - ``ProvisionConfig`` — models/ports, sourced from env with Atlas defaults.
  - ``build_startup_script`` — an **idempotent** bash script JarvisLabs runs on launch to
    install + start the model server(s) bound to 0.0.0.0 and pull/load models.
  - ``classify_endpoints`` — probes the instance's public endpoints to label which is the
    Ollama (``/api/tags``) vs vLLM (``/v1/models``) URL, because JarvisLabs does not expose
    a port→URL mapping and endpoint order is not contractually guaranteed.
"""

from __future__ import annotations

import enum
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

# Canonical serving ports (also the OpenAI-compatible base paths).
OLLAMA_PORT = 11434
VLLM_PORT = 8000


class ServeTarget(enum.Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"
    BOTH = "both"

    @property
    def wants_ollama(self) -> bool:
        return self in (ServeTarget.OLLAMA, ServeTarget.BOTH)

    @property
    def wants_vllm(self) -> bool:
        return self in (ServeTarget.VLLM, ServeTarget.BOTH)

    @classmethod
    def parse(cls, raw: str) -> ServeTarget:
        try:
            return cls(raw.strip().lower())
        except ValueError:
            raise ValueError(
                f"invalid serve target '{raw}' (expected: ollama, vllm, both)"
            ) from None


@dataclass
class ProvisionConfig:
    """Models + ports for provisioning, defaulted from env (Atlas conventions)."""

    target: ServeTarget = ServeTarget.OLLAMA
    chat_model: str = "qwen2.5:3b-instruct"
    embed_model: str = "nomic-embed-text"
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    vllm_max_model_len: int = 8192

    @classmethod
    def from_env(cls, target: ServeTarget, env: dict | None = None) -> ProvisionConfig:
        env = os.environ if env is None else env
        return cls(
            target=target,
            chat_model=env.get("OLLAMA_CHAT_MODEL", cls.chat_model),
            embed_model=env.get("OLLAMA_EMBED_MODEL", cls.embed_model),
            vllm_model=env.get("ATLAS_VLLM_MODEL", cls.vllm_model),
            vllm_max_model_len=int(env.get("ATLAS_VLLM_MAX_MODEL_LEN", cls.vllm_max_model_len)),
        )

    def http_ports(self) -> str:
        ports: list[int] = []
        if self.target.wants_ollama:
            ports.append(OLLAMA_PORT)
        if self.target.wants_vllm:
            ports.append(VLLM_PORT)
        return ",".join(str(p) for p in ports)


# ── startup script ────────────────────────────────────────────────────────────

_OLLAMA_BLOCK = """\
# --- Ollama (OpenAI-compatible on :{port}) ---------------------------------
export OLLAMA_HOST=0.0.0.0:{port}
# install ollama, retrying until the binary actually appears (early-boot races / PATH)
for i in 1 2 3 4 5; do
  command -v ollama >/dev/null 2>&1 && break
  echo "[atlas] installing ollama (attempt $i)"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh || true
  else
    wget -qO- https://ollama.com/install.sh | sh || true
  fi
  sleep 5
done
command -v ollama >/dev/null 2>&1 || echo "[atlas] ERROR: ollama install FAILED"
if ! pgrep -x ollama >/dev/null 2>&1; then
  echo "[atlas] starting ollama serve"
  nohup ollama serve > /var/log/atlas-ollama.log 2>&1 &
fi
# wait for the daemon, then pull models (idempotent — ollama skips if present)
for i in $(seq 1 30); do
  curl -sf "http://127.0.0.1:{port}/api/tags" >/dev/null 2>&1 && break
  sleep 2
done
ollama pull "{chat_model}"
ollama pull "{embed_model}"
echo "[atlas] ollama ready on :{port}"
"""

_VLLM_BLOCK = """\
# --- vLLM (OpenAI-compatible on :{port}) -----------------------------------
if ! python -c "import vllm" >/dev/null 2>&1; then
  echo "[atlas] installing vllm"
  pip install --quiet "vllm>=0.6"
fi
if ! pgrep -f "vllm.entrypoints.openai.api_server" >/dev/null 2>&1; then
  echo "[atlas] starting vllm openai server"
  nohup python -m vllm.entrypoints.openai.api_server \\
    --model "{vllm_model}" --host 0.0.0.0 --port {port} \\
    --max-model-len {max_len} --served-model-name "{vllm_model}" \\
    > /var/log/atlas-vllm.log 2>&1 &
fi
echo "[atlas] vllm starting on :{port} (model load can take several minutes)"
"""


def build_startup_script(config: ProvisionConfig) -> str:
    """Build the idempotent bash startup script for the requested serve target.

    Idempotent because JarvisLabs runs startup scripts on every launch *and* resume:
    installs are guarded by ``command -v`` / import checks, servers by ``pgrep``, and
    ``ollama pull`` is a no-op when the model is already present.
    """
    parts = [
        "#!/bin/bash",
        "set -u",
        # JarvisLabs' headless startup shell has a minimal PATH; add the common bins so the
        # downloader (curl) and the installed ollama (/usr/local/bin) are found. The first
        # live run failed because curl/ollama weren't on PATH here. Verified live 2026-06-29.
        "export PATH=/usr/local/bin:/usr/bin:/bin:/opt/conda/bin:$PATH",
        # capture ALL provisioning output to one inspectable on-box log.
        "exec > /var/log/atlas-provision.log 2>&1",
        "set -x",
        f'echo "[atlas] provisioning serve target: {config.target.value}"',
    ]
    if config.target.wants_ollama:
        parts.append(
            _OLLAMA_BLOCK.format(
                port=OLLAMA_PORT, chat_model=config.chat_model, embed_model=config.embed_model
            )
        )
    if config.target.wants_vllm:
        parts.append(
            _VLLM_BLOCK.format(
                port=VLLM_PORT, vllm_model=config.vllm_model, max_len=config.vllm_max_model_len
            )
        )
    parts.append('echo "[atlas] provisioning script complete"')
    return "\n".join(parts) + "\n"


# ── endpoint discovery (probe-based; order is NOT assumed) ──────────────────────

# probe(url) -> "ollama" | "vllm" | None
EndpointProbe = Callable[[str], "str | None"]


def http_probe(url: str, *, timeout_s: float = 5.0) -> str | None:
    """Classify a public endpoint by hitting both readiness paths.

    Ollama answers ``/api/tags``; an OpenAI-compatible vLLM answers ``/v1/models``. Returns
    the role string, or ``None`` if neither responds (not ready / not that server).
    """
    base = url.rstrip("/")
    if _ok(base + "/api/tags", timeout_s):
        return "ollama"
    if _ok(base + "/v1/models", timeout_s):
        return "vllm"
    return None


def _ok(url: str, timeout_s: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310 - https only
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


def classify_endpoints(
    endpoints: list[str], probe: EndpointProbe = http_probe
) -> dict[str, str]:
    """Map probed endpoints → ``{"ollama": url, "vllm": url}`` (only what responds)."""
    roles: dict[str, str] = {}
    for url in endpoints:
        role = probe(url)
        if role and role not in roles:
            roles[role] = url
    return roles
