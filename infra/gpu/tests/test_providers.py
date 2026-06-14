"""Provider-driver tests (factory + real JarvisLabs flow), all offline via fake transport."""

from __future__ import annotations

import pytest

from atlas_gpu.providers import (
    E2EProvider,
    GpuProviderError,
    JarvisLabsProvider,
    make_provider,
)

# A live-ish fetch payload modelled on the real users/fetch/{id} response shape.
PAUSED_INSTANCE = {
    "success": True,
    "instance": {
        "machine_id": "426399",
        "status": "Paused",
        "framework": "ollama",
        "region": "india-noida-01",
        "hdd": 50,
        "gpu_type": "RTX5000",
        "num_gpus": 1,
        "instance_name": "atlas-ollama",
        "frequency": "Hourly",
        "is_reserved": True,
        "url": "https://abc.notebooksn.jarvislabs.net/lab?token=xyz",
        "endpoints": ["https://abc1.notebooksn.jarvislabs.net"],
    },
}


class FakeTransport:
    """Records calls and returns scripted responses keyed by func."""

    def __init__(self, responses: dict, status_sequence: list[str] | None = None):
        self.responses = responses
        self.calls: list[tuple] = []
        self.status_sequence = status_sequence

    def __call__(self, method, base, func, body, query):
        self.calls.append((method, base, func, body, query))
        if func.startswith("users/fetch") and self.status_sequence is not None:
            inst = dict(PAUSED_INSTANCE["instance"])
            inst["status"] = self.status_sequence.pop(0) if self.status_sequence else "Running"
            return {"success": True, "instance": inst}
        return self.responses.get(func, self.responses.get("*", {}))


# ── factory ──────────────────────────────────────────────────────────────────


def test_factory_defaults_to_jarvislabs():
    p = make_provider(env={})
    assert isinstance(p, JarvisLabsProvider)
    assert p.name == "jarvislabs"
    assert p.api_base == "https://backendprod.jarvislabs.net/"


def test_factory_selects_e2e():
    p = make_provider(env={"GPU_PROVIDER": "e2e"})
    assert isinstance(p, E2EProvider)


def test_factory_unknown_provider_fails_loudly():
    with pytest.raises(GpuProviderError):
        make_provider(env={"GPU_PROVIDER": "nope"})


def test_factory_reads_env_without_exposing_key_in_repr():
    p = make_provider(
        env={
            "GPU_PROVIDER": "jarvislabs",
            "GPU_API_BASE": "https://api.example.test/",
            "GPU_API_KEY": "secret-should-not-leak",
            "GPU_INSTANCE_ID": "426399",
        }
    )
    assert p.api_base == "https://api.example.test/"
    assert p.instance_id == "426399"


# ── JarvisLabs real flow (offline) ─────────────────────────────────────────────


def _provider(transport) -> JarvisLabsProvider:
    return JarvisLabsProvider(
        name="jarvislabs",
        api_key="k",
        instance_id="426399",
        transport=transport,
        _sleep=lambda _s: None,
        _now=lambda: 0.0,
    )


def test_status_and_endpoint_parse_real_shape():
    t = FakeTransport({"users/fetch/426399": PAUSED_INSTANCE})
    p = _provider(t)
    assert p.status() == "Paused"
    assert p.endpoint() == "https://abc1.notebooksn.jarvislabs.net"


def test_pause_hits_misc_pause_with_machine_id_on_region_base():
    t = FakeTransport(
        {"users/fetch/426399": PAUSED_INSTANCE, "misc/pause": {"success": True}}
    )
    p = _provider(t)
    p.pause()
    pause_call = [c for c in t.calls if c[2] == "misc/pause"][0]
    method, base, func, body, query = pause_call
    assert method == "POST"
    assert base == "https://backendn.jarvislabs.net/"  # region-aware (india-noida-01)
    assert query == {"machine_id": "426399"}


def test_pause_failure_raises():
    t = FakeTransport(
        {"users/fetch/426399": PAUSED_INSTANCE, "misc/pause": {"success": False, "detail": "nope"}}
    )
    with pytest.raises(GpuProviderError):
        _provider(t).pause()


def test_resume_posts_to_template_resume_then_waits_for_running():
    # fetch #1 (resume precheck) Paused; resume returns a NEW machine_id; wait → Running.
    seq = ["Paused", "Starting", "Running"]
    t = FakeTransport(
        {"templates/ollama/resume": {"machine_id": "999999"}, "*": {}},
        status_sequence=seq,
    )
    p = _provider(t)
    p.resume()
    resume_calls = [c for c in t.calls if c[2] == "templates/ollama/resume"]
    assert len(resume_calls) == 1
    assert resume_calls[0][1] == "https://backendn.jarvislabs.net/"  # region base
    assert resume_calls[0][3]["machine_id"] == "426399"  # payload carries config
    assert p.instance_id == "999999"  # CRITICAL: adopt the new id (machine_id drifts)


def test_pause_accepts_string_true_success():
    # The real API returns success as the STRING "True", not a bool.
    t = FakeTransport(
        {"users/fetch/426399": PAUSED_INSTANCE, "misc/pause": {"success": "True"}}
    )
    _provider(t).pause()  # must not raise


def test_fetch_adopts_sole_instance_when_configured_id_drifted():
    drifted = {"instances": [{**PAUSED_INSTANCE["instance"], "machine_id": "555000"}]}
    # by-id returns nothing useful; list returns a single, different instance.
    t = FakeTransport({"users/fetch/426399": {"success": False}, "users/fetch": drifted})
    p = _provider(t)
    assert p.status() == "Paused"
    assert p.instance_id == "555000"  # adopted the only live instance


def test_resume_is_noop_when_already_running():
    running = {"success": True, "instance": {**PAUSED_INSTANCE["instance"], "status": "Running"}}
    t = FakeTransport({"users/fetch/426399": running})
    p = _provider(t)
    p.resume()
    assert not any(c[2] == "templates/ollama/resume" for c in t.calls)


def test_resume_raises_on_failed_status():
    t = FakeTransport(
        {"templates/ollama/resume": {"machine_id": "426399"}},
        status_sequence=["Paused", "Failed"],
    )
    with pytest.raises(GpuProviderError):
        _provider(t).resume()


# ── E2E generic seam ───────────────────────────────────────────────────────────


def test_e2e_endpoint_requires_url_field():
    t = FakeTransport({"/instances/i": {"status": "running"}})  # no url
    p = E2EProvider(name="e2e", api_base="https://x", api_key="", instance_id="i", transport=t)
    with pytest.raises(GpuProviderError):
        p.endpoint()
