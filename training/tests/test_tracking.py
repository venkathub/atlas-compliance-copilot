"""Offline, GPU-free unit tests for the MLflow/HF tracking wrapper (P6 Task 7b).

mlflow and huggingface_hub are never imported here — the heavy clients are injected as fakes.
Asserts the registration source is the HF repo+revision (durable, off-GPU), not a local path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_training.config import load
from atlas_training.tracking import (
    ModelVersion,
    Tracker,
    TrackingError,
    hf_source_uri,
    is_hf_source,
    run_params,
)

CONFIG = Path(__file__).resolve().parent.parent / "configs" / "qlora_qwen7b.yaml"


class FakeRegistry:
    def __init__(self):
        self.experiment = None
        self.run_id = None
        self.params = {}
        self.metrics = []
        self.versions = []
        self.ended = False

    def set_experiment(self, name):
        self.experiment = name

    def start_run(self, run_name):
        self.run_id = f"run-{run_name}"
        return self.run_id

    def log_params(self, params):
        self.params.update(params)

    def log_metrics(self, metrics, step=None):
        self.metrics.append((step, dict(metrics)))

    def end_run(self):
        self.ended = True

    def create_model_version(self, name, source, run_id):
        self.versions.append((name, source, run_id))
        return str(len(self.versions))


class FakeHub:
    def __init__(self, revision="abc123sha"):
        self.revision = revision
        self.calls = []

    def push(self, adapter_path, repo, *, private, token):
        self.calls.append({"path": adapter_path, "repo": repo, "private": private, "token": token})
        return self.revision


@pytest.fixture
def config():
    return load(CONFIG)


# ── pure helpers ─────────────────────────────────────────────────────────────────────────────────


def test_hf_source_uri():
    assert hf_source_uri("user/adapter", "abc123") == "hf://user/adapter@abc123"
    assert is_hf_source("hf://user/adapter@abc123")
    assert not is_hf_source("/local/gpu/path/adapter")
    assert not is_hf_source("hf://user/adapter")  # no revision


def test_hf_source_uri_rejects_empty():
    with pytest.raises(TrackingError):
        hf_source_uri("user/adapter", "")


def test_run_params_flattens_config(config):
    p = run_params(config, prompt_template_sha="deadbeef")
    assert p["base_model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert p["seed"] == 42
    assert p["quant.bnb_4bit_quant_type"] == "nf4"
    assert p["dataset.prompt_template_sha"] == "deadbeef"


# ── Tracker orchestration ─────────────────────────────────────────────────────────────────────


def test_log_run_sets_experiment_and_params(config):
    reg, hub = FakeRegistry(), FakeHub()
    t = Tracker(registry=reg, hub=hub, hf_repo="u/a", hf_token="tok")
    run_id = t.log_run(config, prompt_template_sha="sha1")
    assert reg.experiment == config.mlflow.experiment
    assert run_id == reg.run_id
    assert reg.params["base_model"] == config.base_model
    assert reg.params["dataset.prompt_template_sha"] == "sha1"


def test_log_loss_records_train_and_eval(config):
    reg, hub = FakeRegistry(), FakeHub()
    t = Tracker(registry=reg, hub=hub, hf_repo="u/a", hf_token="tok")
    t.log_loss(1, train_loss=2.0, eval_loss=2.5)
    t.log_loss(2, train_loss=1.5)
    assert reg.metrics[0] == (1, {"train_loss": 2.0, "eval_loss": 2.5})
    assert reg.metrics[1] == (2, {"train_loss": 1.5})


def test_register_adapter_pushes_then_registers_with_hf_source(config, tmp_path):
    reg, hub = FakeRegistry(), FakeHub(revision="rev-9f")
    t = Tracker(registry=reg, hub=hub, hf_repo="u/adapter", hf_token="tok", hf_private=True)
    run_id = t.log_run(config)
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    mv = t.register_adapter(run_id, adapter, config.mlflow.register_as)

    assert isinstance(mv, ModelVersion)
    # pushed to HF before registering
    assert hub.calls[0]["repo"] == "u/adapter"
    assert hub.calls[0]["private"] is True
    # registered version's source is the HF repo+revision — NOT a local/GPU path
    assert mv.source == "hf://u/adapter@rev-9f"
    assert is_hf_source(mv.source)
    assert str(adapter) not in mv.source
    assert reg.versions[0] == (config.mlflow.register_as, "hf://u/adapter@rev-9f", run_id)
    assert reg.ended is True


def test_register_refuses_non_hf_source(config, tmp_path, monkeypatch):
    # A hub that returns an empty revision must not yield a registerable (local-ish) source.
    reg, hub = FakeRegistry(), FakeHub(revision="")
    t = Tracker(registry=reg, hub=hub, hf_repo="u/a", hf_token="tok")
    with pytest.raises(TrackingError):
        t.register_adapter("run-1", tmp_path, config.mlflow.register_as)


# ── from_env wiring ──────────────────────────────────────────────────────────────────────────────


def test_from_env_requires_repo_and_token(monkeypatch):
    monkeypatch.delenv("ATLAS_HF_ADAPTER_REPO", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(TrackingError, match="ATLAS_HF_ADAPTER_REPO"):
        Tracker.from_env(FakeRegistry(), FakeHub())
    monkeypatch.setenv("ATLAS_HF_ADAPTER_REPO", "u/a")
    with pytest.raises(TrackingError, match="HF_TOKEN"):
        Tracker.from_env(FakeRegistry(), FakeHub())


def test_from_env_reads_private_flag(monkeypatch):
    monkeypatch.setenv("ATLAS_HF_ADAPTER_REPO", "u/a")
    monkeypatch.setenv("HF_TOKEN", "tok")
    monkeypatch.setenv("HF_PRIVATE", "false")
    t = Tracker.from_env(FakeRegistry(), FakeHub())
    assert t.hf_private is False
    assert t.hf_repo == "u/a"
