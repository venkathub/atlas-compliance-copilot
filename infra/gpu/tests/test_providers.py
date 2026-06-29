"""Provider tests (SDK-backed) — all offline via FakeJlClient + a deterministic probe."""

from __future__ import annotations

import pytest

from atlas_gpu.providers import CreateSpec, JarvisLabsProvider, make_provider
from atlas_gpu.provision import ProvisionConfig, ServeTarget
from atlas_gpu.sdk import JlError
from tests.fakes import DEFAULT_PROBE, FakeJlClient, role_probe


def _provider(client: FakeJlClient, instance_id: str = "", **spec) -> JarvisLabsProvider:
    return JarvisLabsProvider(
        name="jarvislabs",
        client=client,
        instance_id=instance_id,
        create_spec=CreateSpec(**spec) if spec else CreateSpec(),
        probe=DEFAULT_PROBE,
    )


# ── factory ──────────────────────────────────────────────────────────────────


def test_factory_defaults_to_jarvislabs():
    p = make_provider(env={"GPU_INSTANCE_ID": "42"})
    assert p.name == "jarvislabs"
    assert p.instance_id == "42"


def test_factory_unknown_provider_fails_loudly():
    with pytest.raises(JlError):
        make_provider(env={"GPU_PROVIDER": "nope"})


def test_factory_reads_create_spec_from_env():
    p = make_provider(env={"GPU_TYPE": "L4", "GPU_STORAGE_GB": "80"})
    assert p.create_spec.gpu_type == "L4"
    assert p.create_spec.storage_gb == 80


# ── lifecycle ────────────────────────────────────────────────────────────────


def test_status_reads_instance():
    c = FakeJlClient(status="Paused")
    c.seed("500", "Paused")
    assert _provider(c, "500").status() == "Paused"


def test_resume_skips_when_already_running():
    c = FakeJlClient()
    c.seed("500", "Running")
    p = _provider(c, "500")
    p.resume()
    assert c.resumed == []  # no resume call needed
    assert p.instance_id == "500"


def test_resume_adopts_new_machine_id():
    c = FakeJlClient()
    c.seed("500", "Paused")
    p = _provider(c, "500")
    p.resume()
    assert len(c.resumed) == 1
    assert p.instance_id != "500"  # adopted the new id JarvisLabs assigned


def test_pause_and_destroy_call_client():
    c = FakeJlClient()
    p = _provider(c, "500")
    p.pause()
    p.destroy()
    assert c.paused == ["500"]
    assert c.destroyed == ["500"]


def test_pause_without_id_raises():
    with pytest.raises(JlError):
        _provider(FakeJlClient(), "").pause()


def test_endpoint_classifies_via_probe():
    c = FakeJlClient(endpoints=["https://gen-6006.x", "https://node-ollama.x"])
    p = _provider(c, "500")
    assert p.endpoint() == "https://node-ollama.x"


def test_endpoint_prefers_ollama_then_vllm():
    c = FakeJlClient(endpoints=["https://node-vllm.x"])
    p = _provider(c, "500")
    assert p.endpoint() == "https://node-vllm.x"  # falls back to vllm when no ollama


def test_endpoint_raises_when_nothing_ready():
    c = FakeJlClient(endpoints=["https://gen-6006.x"])  # neither ollama nor vllm
    p = _provider(c, "500")
    with pytest.raises(JlError):
        p.endpoint()


def test_discover_caches_until_refresh():
    c = FakeJlClient(endpoints=["https://node-ollama.x"])
    c.seed("500", "Running")
    p = _provider(c, "500")
    first = p.discover_endpoints()
    assert first == {"ollama": "https://node-ollama.x"}
    # change endpoints; cached result stays until refresh=True
    c.instances["500"].endpoints = ["https://node-vllm.x"]
    assert p.discover_endpoints() == first
    assert p.discover_endpoints(refresh=True) == {"vllm": "https://node-vllm.x"}


# ── create (from scratch) ─────────────────────────────────────────────────────


def test_create_uploads_script_and_sets_ports_for_target():
    c = FakeJlClient()
    p = _provider(c, gpu_type="A100", storage_gb=100)
    info = p.create(ProvisionConfig(target=ServeTarget.BOTH))
    # uploaded a startup script
    assert len(c.scripts) == 1
    name, sid, body = c.scripts[0]
    assert "atlas-provision-both" in name
    assert "ollama" in body and "vllm" in body
    # created with both ports and the script id
    assert c.created["http_ports"] == "11434,8000"
    assert c.created["script_id"] == sid
    assert c.created["gpu_type"] == "A100"
    # adopted the new machine id
    assert p.instance_id == info.machine_id


def test_create_ollama_only_exposes_single_port():
    c = FakeJlClient()
    p = _provider(c)
    p.create(ProvisionConfig(target=ServeTarget.OLLAMA))
    assert c.created["http_ports"] == "11434"
    assert "vllm" not in c.scripts[0][2]


def test_create_twice_reuses_startup_script_no_duplicates():
    # Regression for the live-found script-accumulation cap (ADR-0066): re-provisioning
    # must upsert the startup script by name, not pile up a new one each time.
    c = FakeJlClient()
    p = _provider(c)
    p.create(ProvisionConfig(target=ServeTarget.OLLAMA))
    p.create(ProvisionConfig(target=ServeTarget.OLLAMA))
    names = [n for (n, _sid, _body) in c.scripts]
    assert names.count("atlas-provision-ollama") == 1


def test_probe_substring_helper():
    probe = role_probe({"11434": "ollama", "8000": "vllm"})
    assert probe("https://x-11434.y") == "ollama"
    assert probe("https://x-8000.y") == "vllm"
    assert probe("https://x-6006.y") is None
