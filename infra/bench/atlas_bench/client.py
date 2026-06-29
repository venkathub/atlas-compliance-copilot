"""Live HTTP client: streams an OpenAI-compatible chat completion and times it.

Used only in real (GPU-on) runs — never imported by the offline unit tests, which inject a
fake ``send``. Works unchanged against Ollama and vLLM because both expose
``POST /v1/chat/completions`` with SSE streaming; that interchangeability is the whole point
of the Ollama↔vLLM comparison.

Token accounting: we prefer the server-reported ``usage.completion_tokens`` (vLLM emits it
with ``stream_options.include_usage``; Ollama returns ``eval_count`` on its native API but
not always via the OpenAI shape), and fall back to counting streamed content deltas as a
proxy. The fallback is approximate and is flagged as such in the report.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from atlas_bench.metrics import RequestResult
from atlas_bench.runner import SendFn


@dataclass
class ChatClientConfig:
    base_url: str
    model: str
    max_tokens: int = 256
    temperature: float = 0.0
    timeout_s: float = 120.0
    api_key: str = "not-needed"  # self-hosted endpoints ignore it; header kept for parity


def _count_delta_tokens(text: str) -> int:
    """Cheap proxy token count for the fallback path (~whitespace words)."""
    return len(text.split())


async def _stream_one(
    client: httpx.AsyncClient, cfg: ChatClientConfig, prompt: str
) -> RequestResult:
    body = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    start = time.monotonic()
    ttft: float | None = None
    reported_tokens: int | None = None
    proxy_tokens = 0
    try:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
        ) as resp:
            if resp.status_code != 200:
                await resp.aread()
                return RequestResult(
                    ok=False, latency_s=time.monotonic() - start,
                    error=f"HTTP {resp.status_code}",
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if choices:
                    delta = (choices[0].get("delta") or {}).get("content") or ""
                    if delta:
                        if ttft is None:
                            ttft = time.monotonic() - start
                        proxy_tokens += _count_delta_tokens(delta)
                usage = chunk.get("usage")
                if isinstance(usage, dict) and usage.get("completion_tokens") is not None:
                    reported_tokens = int(usage["completion_tokens"])
    except (httpx.HTTPError, httpx.StreamError) as e:
        return RequestResult(ok=False, latency_s=time.monotonic() - start, error=type(e).__name__)

    latency = time.monotonic() - start
    tokens = reported_tokens if reported_tokens is not None else proxy_tokens
    return RequestResult(ok=True, latency_s=latency, ttft_s=ttft, output_tokens=tokens)


def make_send(
    cfg: ChatClientConfig, *, max_connections: int
) -> tuple[SendFn, httpx.AsyncClient]:
    """Build a ``send`` coroutine + the AsyncClient backing it (caller must aclose it).

    The connection pool is sized to the concurrency level so the client itself is never the
    bottleneck that limits in-flight requests.
    """
    limits = httpx.Limits(
        max_connections=max_connections, max_keepalive_connections=max_connections
    )
    client = httpx.AsyncClient(
        base_url=cfg.base_url.rstrip("/"), timeout=cfg.timeout_s, limits=limits
    )

    async def send(prompt: str) -> RequestResult:
        return await _stream_one(client, cfg, prompt)

    return send, client


DEFAULT_PROMPTS: Sequence[str] = (
    "Summarize the key obligations in a standard NDA in three bullet points.",
    "Explain what a SOC 2 Type II report attests to, in two sentences.",
    "List three controls that mitigate insider trading risk at a brokerage.",
    "What is the difference between data residency and data sovereignty?",
)
