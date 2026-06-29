"""Provisioning unit tests: serve targets, startup-script builder, endpoint classify."""

from __future__ import annotations

import pytest

from atlas_gpu.provision import (
    ProvisionConfig,
    ServeTarget,
    build_startup_script,
    classify_endpoints,
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


def test_classify_endpoints_probes_not_order():
    eps = ["https://gen-6006.x", "https://node-vllm.x", "https://node-ollama.x"]
    roles = classify_endpoints(eps, role_probe({"ollama": "ollama", "vllm": "vllm"}))
    assert roles == {"vllm": "https://node-vllm.x", "ollama": "https://node-ollama.x"}


def test_classify_endpoints_ignores_unready():
    eps = ["https://gen-6006.x"]  # probe returns None
    assert classify_endpoints(eps, role_probe({"ollama": "ollama"})) == {}
