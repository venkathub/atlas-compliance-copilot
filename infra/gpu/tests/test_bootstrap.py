"""Bootstrap (E2E provisioning) tests — offline via FakeJlClient + injected clock/probe."""

from __future__ import annotations

import pytest

from atlas_gpu.bootstrap import provision_from_scratch, wait_for_roles, write_env
from atlas_gpu.providers import CreateSpec, JarvisLabsProvider
from atlas_gpu.provision import ProvisionConfig, ServeTarget
from tests.fakes import DEFAULT_PROBE, FakeJlClient, role_probe


def _provider(client: FakeJlClient, probe=DEFAULT_PROBE, instance_id="") -> JarvisLabsProvider:
    return JarvisLabsProvider(
        name="jarvislabs", client=client, instance_id=instance_id,
        create_spec=CreateSpec(gpu_type="A100", storage_gb=100), probe=probe,
    )


# ── write_env ────────────────────────────────────────────────────────────────


def test_write_env_appends_then_updates(tmp_path):
    f = tmp_path / ".env"
    f.write_text("EXISTING=1\n")
    write_env(str(f), "OLLAMA_BASE_URL", "https://a.x")
    assert "OLLAMA_BASE_URL=https://a.x" in f.read_text()
    write_env(str(f), "OLLAMA_BASE_URL", "https://b.x")  # update in place
    body = f.read_text()
    assert "https://b.x" in body and "https://a.x" not in body
    assert "EXISTING=1" in body  # other lines preserved


# ── wait_for_roles ───────────────────────────────────────────────────────────


def test_wait_for_roles_ready_after_retries():
    c = FakeJlClient(endpoints=["https://node-ollama.x"])
    state = {"ready": False}
    p = _provider(c, probe=lambda u: "ollama" if state["ready"] else None, instance_id="500")
    clock = {"t": 0.0}
    calls = {"n": 0}

    def sleep(s):
        calls["n"] += 1
        clock["t"] += s
        if calls["n"] >= 3:
            state["ready"] = True

    roles = wait_for_roles(
        p, ServeTarget.OLLAMA, ready_timeout_s=100, poll_interval_s=10,
        sleep=sleep, now=lambda: clock["t"],
    )
    assert roles == {"ollama": "https://node-ollama.x"}
    assert calls["n"] >= 3


def test_wait_for_roles_times_out():
    c = FakeJlClient(endpoints=["https://gen-6006.x"])
    p = _provider(c, probe=lambda _u: None, instance_id="500")
    clock = {"t": 0.0}
    with pytest.raises(TimeoutError):
        wait_for_roles(
            p, ServeTarget.OLLAMA, ready_timeout_s=30, poll_interval_s=10,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s), now=lambda: clock["t"],
        )


def test_wait_for_roles_requires_all_targets_for_both():
    # only ollama responds; target=both must keep waiting → timeout
    c = FakeJlClient(endpoints=["https://node-ollama.x"])
    p = _provider(c, probe=role_probe({"ollama": "ollama"}), instance_id="500")
    clock = {"t": 0.0}
    with pytest.raises(TimeoutError):
        wait_for_roles(
            p, ServeTarget.BOTH, ready_timeout_s=20, poll_interval_s=10,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s), now=lambda: clock["t"],
        )


# ── provision_from_scratch ────────────────────────────────────────────────────


def test_dry_run_builds_script_without_creating():
    c = FakeJlClient()
    p = _provider(c)
    res = provision_from_scratch(p, ProvisionConfig(target=ServeTarget.BOTH), dry_run=True)
    assert res.dry_run is True
    assert "ollama serve" in res.script and "vllm" in res.script
    assert c.created is None  # nothing created
    assert c.scripts == []


def test_full_provision_writes_env_and_returns_urls(tmp_path):
    c = FakeJlClient(endpoints=["https://gen-6006.x", "https://node-ollama.x"])
    p = _provider(c)
    env_file = tmp_path / ".env"
    res = provision_from_scratch(
        p, ProvisionConfig(target=ServeTarget.OLLAMA), env_file=str(env_file),
    )
    assert res.ollama_base_url == "https://node-ollama.x"
    assert res.vllm_base_url is None
    assert res.machine_id == p.instance_id
    body = env_file.read_text()
    assert "OLLAMA_BASE_URL=https://node-ollama.x" in body
    assert f"GPU_INSTANCE_ID={p.instance_id}" in body
    assert c.created is not None  # an instance was created


def test_full_provision_both_writes_both_urls(tmp_path):
    c = FakeJlClient(endpoints=["https://node-ollama.x", "https://node-vllm.x"])
    p = _provider(c)
    env_file = tmp_path / ".env"
    res = provision_from_scratch(
        p, ProvisionConfig(target=ServeTarget.BOTH), env_file=str(env_file),
    )
    assert res.ollama_base_url == "https://node-ollama.x"
    assert res.vllm_base_url == "https://node-vllm.x"
    body = env_file.read_text()
    assert "OLLAMA_BASE_URL=https://node-ollama.x" in body
    assert "ATLAS_VLLM_BASE_URL=https://node-vllm.x" in body
