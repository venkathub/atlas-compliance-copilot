"""Opt-in @live smoke: vLLM multi-LoRA serves base + adapter as distinct model names (P7 Task 9).

NOT in CI (needs a live GPU endpoint). Enable with a running vLLM multi-LoRA server (brought up by
the provisioner with ATLAS_VLLM_ENABLE_LORA=true — infra/gpu README) and:

    ATLAS_GPU_LIVE=1 ATLAS_VLLM_BASE_URL=https://<host>/v1 \
        ATLAS_VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ \
        ATLAS_ROUTER_FT_TIER_MODEL=atlas-citation-adapter \
        uv run --directory infra/gpu --with pytest pytest tests/test_vllm_lora_live.py -q

Proves (R6, train–serve skew): the SAME served endpoint exposes both the base and the fine-tuned
adapter, and a chat completion works through each. Teardown stays the provisioner's job
(`atlas_gpu teardown --destroy`) — this smoke only reads the live endpoint. Uses stdlib urllib only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ATLAS_GPU_LIVE") != "1",
    reason="live vLLM multi-LoRA smoke is opt-in (set ATLAS_GPU_LIVE=1 with a running endpoint)",
)


def _base_url() -> str:
    url = os.environ.get("ATLAS_VLLM_BASE_URL")
    if not url:
        pytest.skip("ATLAS_VLLM_BASE_URL unset")
    return url.rstrip("/")


def _get_json(url: str, timeout_s: float = 30.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        return json.loads(resp.read())


def _chat(base: str, model: str, timeout_s: float = 120.0) -> tuple[str, float]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        "max_tokens": 8,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body, headers={"Content-Type": "application/json"}
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        out = json.loads(resp.read())
    latency_ms = (time.monotonic() - start) * 1000.0
    return out["choices"][0]["message"]["content"], latency_ms


def test_base_and_adapter_are_both_served():
    base = _base_url()
    served = {m["id"] for m in _get_json(base + "/models").get("data", [])}
    base_model = os.environ["ATLAS_VLLM_MODEL"]
    adapter = os.environ["ATLAS_ROUTER_FT_TIER_MODEL"]
    assert base_model in served, f"base {base_model!r} not in served models {served}"
    assert adapter in served, f"adapter {adapter!r} not in served models {served}"


def test_chat_completion_through_base_and_adapter():
    base = _base_url()
    base_model = os.environ["ATLAS_VLLM_MODEL"]
    adapter = os.environ["ATLAS_ROUTER_FT_TIER_MODEL"]

    base_text, base_ms = _chat(base, base_model)
    ft_text, ft_ms = _chat(base, adapter)

    assert base_text.strip(), "base model returned empty content"
    assert ft_text.strip(), "adapter returned empty content"
    # Latency is recorded for the cost/latency evidence (report-only here).
    print(f"base latency={base_ms:.0f}ms ft latency={ft_ms:.0f}ms")
