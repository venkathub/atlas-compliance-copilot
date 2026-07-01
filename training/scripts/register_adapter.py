"""Register the committed HF adapter as an MLflow model version (laptop-side, GPU-free).

The episodic run pushes the adapter to the HF Hub (durable) and records the HF repo+revision in
`results/comparison.json` (`model_ids.ft = hf://<repo>@<rev>`). This one-shot registers that as an
MLflow registry version whose **source is the HF URI** — so the registry points at the durable,
GPU-decoupled artifact. Run it after the MLflow service is up:

    docker compose -f infra/docker-compose.yml up -d mlflow
    MLFLOW_TRACKING_URI=http://localhost:5000 \
        uv run --directory training --group train python scripts/register_adapter.py

Reuses atlas_training.tracking.MlflowRegistry (the same wrapper unit-tested + exercised by the
opt-in live IT). No GPU; no model download — pure metadata pointing at HF.
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results" / "comparison.json"
REGISTERED_NAME = "atlas-citation-adapter"
EXPERIMENT = "atlas-citation-ft"


def main() -> int:
    from atlas_training.tracking import MlflowRegistry, is_hf_source

    comp = json.loads(RESULTS.read_text(encoding="utf-8"))
    source = comp["model_ids"]["ft"]  # hf://<repo>@<rev>
    if not is_hf_source(source):
        raise SystemExit(f"refusing to register non-HF source: {source!r}")

    reg = MlflowRegistry()
    reg.set_experiment(EXPERIMENT)
    run_id = reg.start_run("p6-register-adapter")
    reg.log_params({
        "base_model": comp["model_ids"]["base"],
        "dataset_size": comp["dataset_size"],
        "git_sha": comp["git_sha"],
        **{f"metric.{k}.ft": v["ft"] for k, v in comp["metrics"].items()},
        **{f"metric.{k}.delta": v["delta"] for k, v in comp["metrics"].items()},
    })
    version = reg.create_model_version(REGISTERED_NAME, source, run_id)
    reg.end_run()
    print(f"registered {REGISTERED_NAME} v{version} <- {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
