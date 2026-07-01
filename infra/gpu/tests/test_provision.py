"""Provisioning unit tests: serve targets, startup-script builder, endpoint classify."""

from __future__ import annotations

import pytest

from atlas_gpu.provision import (
    ProvisionConfig,
    ServeTarget,
    build_startup_script,
    classify_endpoints,
    lora_load_payload,
)
from tests.fakes import role_probe


def test_serve_target_parse_and_flags():
    assert ServeTarget.parse("OLLAMA") is ServeTarget.OLLAMA
    assert ServeTarget.parse("both").wants_ollama
    assert ServeTarget.parse("both").wants_vllm
    assert ServeTarget.VLLM.wants_ollama is False
    with pytest.raises(ValueError):
        ServeTarget.parse("gguf")


def test_http_ports_per_target():
    assert ProvisionConfig(target=ServeTarget.OLLAMA).http_ports() == "11434"
    assert ProvisionConfig(target=ServeTarget.VLLM).http_ports() == "8000"
    assert ProvisionConfig(target=ServeTarget.BOTH).http_ports() == "11434,8000"


def test_config_from_env_overrides():
    cfg = ProvisionConfig.from_env(
        ServeTarget.BOTH,
        env={"OLLAMA_CHAT_MODEL": "qwen2.5:7b-instruct", "ATLAS_VLLM_MODEL": "my/model"},
    )
    assert cfg.chat_model == "qwen2.5:7b-instruct"
    assert cfg.vllm_model == "my/model"


def test_startup_script_ollama_only():
    script = build_startup_script(ProvisionConfig(target=ServeTarget.OLLAMA))
    assert script.startswith("#!/bin/bash")
    # /usr/local/bin must be on PATH — JarvisLabs' headless startup shell omits it and
    # ollama installs there (regression guard for the live-found bug, ADR-0066).
    assert "/usr/local/bin" in script and "export PATH=" in script
    # all output captured to one inspectable provisioning log
    assert "/var/log/atlas-provision.log" in script
    assert "ollama serve" in script
    assert "ollama pull" in script
    assert "vllm" not in script
    # idempotency guards present
    assert "command -v ollama" in script
    assert "pgrep -x ollama" in script


def test_startup_script_vllm_only():
    script = build_startup_script(ProvisionConfig(target=ServeTarget.VLLM))
    assert "vllm.entrypoints.openai.api_server" in script
    assert "pip install" in script
    assert "ollama serve" not in script


def test_startup_script_both_has_both_servers():
    script = build_startup_script(ProvisionConfig(target=ServeTarget.BOTH))
    assert "ollama serve" in script
    assert "vllm.entrypoints.openai.api_server" in script


def test_vllm_no_lora_flags_when_disabled():
    # Default (LoRA off): the serve command carries NO multi-LoRA flags — byte-identical to before.
    script = build_startup_script(ProvisionConfig(target=ServeTarget.VLLM))
    assert "--enable-lora" not in script
    assert "--lora-modules" not in script
    assert "VLLM_ALLOW_RUNTIME_LORA_UPDATING" not in script


def test_vllm_multi_lora_flags_when_enabled():
    cfg = ProvisionConfig(
        target=ServeTarget.VLLM,
        vllm_enable_lora=True,
        vllm_lora_modules="atlas-citation-adapter=/workspace/adapter",
        vllm_max_loras=2,
        vllm_max_lora_rank=16,
    )
    script = build_startup_script(cfg)
    assert "--enable-lora" in script
    assert "--max-loras 2" in script
    assert "--max-lora-rank 16" in script
    assert "--lora-modules atlas-citation-adapter=/workspace/adapter" in script
    # base + adapter on one endpoint; the served base name is still present.
    assert '--served-model-name "Qwen/Qwen2.5-7B-Instruct-AWQ"' in script


def test_vllm_runtime_lora_env_gated():
    off = build_startup_script(ProvisionConfig(target=ServeTarget.VLLM, vllm_enable_lora=True))
    assert "VLLM_ALLOW_RUNTIME_LORA_UPDATING" not in off
    on = build_startup_script(ProvisionConfig(
        target=ServeTarget.VLLM, vllm_enable_lora=True, vllm_runtime_lora=True))
    assert "export VLLM_ALLOW_RUNTIME_LORA_UPDATING=1" in on


def test_lora_flags_absent_when_target_is_ollama_only():
    # LoRA env set but serving ollama only → no vLLM block, so no LoRA flags leak in.
    cfg = ProvisionConfig(target=ServeTarget.OLLAMA, vllm_enable_lora=True,
                          vllm_lora_modules="a=/p", vllm_runtime_lora=True)
    script = build_startup_script(cfg)
    assert "--enable-lora" not in script
    assert "VLLM_ALLOW_RUNTIME_LORA_UPDATING" not in script


def test_provision_config_from_env_parses_lora_knobs():
    cfg = ProvisionConfig.from_env(
        ServeTarget.VLLM,
        env={
            "ATLAS_VLLM_ENABLE_LORA": "true",
            "ATLAS_VLLM_LORA_MODULES": "atlas-citation-adapter=/workspace/adapter",
            "ATLAS_VLLM_MAX_LORAS": "3",
            "ATLAS_VLLM_MAX_LORA_RANK": "32",
            "ATLAS_VLLM_RUNTIME_LORA": "1",
        },
    )
    assert cfg.vllm_enable_lora is True
    assert cfg.vllm_lora_modules == "atlas-citation-adapter=/workspace/adapter"
    assert cfg.vllm_max_loras == 3
    assert cfg.vllm_max_lora_rank == 32
    assert cfg.vllm_runtime_lora is True


def test_provision_config_from_env_lora_defaults_off():
    cfg = ProvisionConfig.from_env(ServeTarget.VLLM, env={})
    assert cfg.vllm_enable_lora is False
    assert cfg.vllm_runtime_lora is False
    assert cfg.vllm_max_lora_rank == 16


def test_lora_load_payload_shape():
    assert lora_load_payload("atlas-citation-adapter", "/workspace/adapter") == {
        "lora_name": "atlas-citation-adapter",
        "lora_path": "/workspace/adapter",
    }


def test_lora_load_payload_requires_both():
    with pytest.raises(ValueError, match="needs both name and path"):
        lora_load_payload("", "/p")


def test_classify_endpoints_probes_not_order():
    eps = ["https://gen-6006.x", "https://node-vllm.x", "https://node-ollama.x"]
    roles = classify_endpoints(eps, role_probe({"ollama": "ollama", "vllm": "vllm"}))
    assert roles == {"vllm": "https://node-vllm.x", "ollama": "https://node-ollama.x"}


def test_classify_endpoints_ignores_unready():
    eps = ["https://gen-6006.x"]  # probe returns None
    assert classify_endpoints(eps, role_probe({"ollama": "ollama"})) == {}
