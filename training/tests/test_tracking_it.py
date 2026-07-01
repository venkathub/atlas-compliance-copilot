"""Live MLflow round-trip integration test (P6 Task 7b) — OPT-IN, not in CI.

Requires a running local `mlflow` container (infra/, `docker compose up mlflow`) and the `train`
dependency group (mlflow installed). The HF push stays a fake (no network/secret). Enable with:

    ATLAS_MLFLOW_IT=1 MLFLOW_TRACKING_URI=http://localhost:5000 \
        uv run --directory training --group train pytest tests/test_tracking_it.py -q

CPU-only — there is no GPU in this test. It proves: log a run, register a version whose source is
an HF repo+revision, read it back from the registry.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from atlas_training.config import load
from atlas_training.tracking import Tracker, is_hf_source

pytestmark = pytest.mark.skipif(
    os.environ.get("ATLAS_MLFLOW_IT") != "1",
    reason="live MLflow IT is opt-in (set ATLAS_MLFLOW_IT=1 with a running mlflow container)",
)

CONFIG = Path(__file__).resolve().parent.parent / "configs" / "qlora_qwen3b_smoke.yaml"


class FakeHub:
    def push(self, adapter_path, repo, *, private, token):
        return "itrev-deadbeef"


def test_live_mlflow_round_trip(tmp_path):
    from atlas_training.tracking import MlflowRegistry  # imports mlflow (train group)

    registry = MlflowRegistry()
    tracker = Tracker(registry=registry, hub=FakeHub(), hf_repo="atlas-it/adapter", hf_token="tok")

    config = load(CONFIG)
    run_id = tracker.log_run(config, prompt_template_sha="itsha")
    tracker.log_loss(1, train_loss=2.0, eval_loss=2.4)

    adapter = tmp_path / "adapter"
    adapter.mkdir()
    mv = tracker.register_adapter(run_id, adapter, config.mlflow.register_as)

    assert is_hf_source(mv.source)
    assert mv.source == "hf://atlas-it/adapter@itrev-deadbeef"

    # read it back from the registry
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    fetched = client.get_model_version(config.mlflow.register_as, mv.version)
    assert fetched.source == mv.source
    assert fetched.run_id == run_id


def test_live_promote_rollback_round_trip(tmp_path):
    """Register two versions, promote each, roll back — assert @champion resolves correctly."""
    from atlas_training.tracking import (
        MlflowRegistry,
        promote,
        rollback,
    )

    registry = MlflowRegistry()
    tracker = Tracker(registry=registry, hub=FakeHub(), hf_repo="atlas-it/adapter", hf_token="tok")
    config = load(CONFIG)
    name = config.mlflow.register_as

    # register two versions of the same registered model
    run1 = tracker.log_run(config, prompt_template_sha="v1")
    (tmp_path / "a").mkdir()
    v1 = tracker.register_adapter(run1, tmp_path / "a", name).version
    run2 = tracker.log_run(config, prompt_template_sha="v2")
    (tmp_path / "b").mkdir()
    v2 = tracker.register_adapter(run2, tmp_path / "b", name).version

    # promote v1, then v2 (v1 becomes the rollback target)
    promote(registry, name, v1)
    assert registry.get_version_by_alias(name, "champion") == v1
    out = promote(registry, name, v2)
    assert registry.get_version_by_alias(name, "champion") == v2
    assert out.previous == v1

    # rollback restores v1
    rb = rollback(registry, name)
    assert rb.champion == v1
    assert registry.get_version_by_alias(name, "champion") == v1
