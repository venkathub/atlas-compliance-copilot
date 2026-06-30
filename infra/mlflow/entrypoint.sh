#!/usr/bin/env sh
# Atlas P6 — MLflow server entrypoint (ADR-0072). All config is env-driven; no secrets baked in.
#   MLFLOW_BACKEND_STORE_URI  Postgres metadata store (run/registry), e.g.
#                             postgresql://user:pass@postgres:5432/mlflow
#   MLFLOW_ARTIFACT_ROOT      server-side artifact destination (a mounted volume). The fine-tuned
#                             adapter is NOT stored here — it is pushed to the HF Hub; this root
#                             only holds incidental run artifacts (loss curves, params files).
set -eu

: "${MLFLOW_BACKEND_STORE_URI:?MLFLOW_BACKEND_STORE_URI is required}"
: "${MLFLOW_ARTIFACT_ROOT:=/mlflow/artifacts}"

mkdir -p "${MLFLOW_ARTIFACT_ROOT}"

exec mlflow server \
  --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
  --artifacts-destination "${MLFLOW_ARTIFACT_ROOT}" \
  --host 0.0.0.0 \
  --port 5000
