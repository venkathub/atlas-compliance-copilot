# Atlas P6 — MLflow tracking server + model registry (ADR-0072).
# Self-hosted, Postgres-backed (mirrors the Langfuse "reuse atlas-postgres" footprint,
# ADR-0025). Stores run/registry METADATA in the `mlflow` db; durable model artifacts
# live on the Hugging Face Hub (the registry version's source is the HF repo+revision),
# so a disposable GPU never holds the only copy of the adapter.
#
# Pinned, slim, no GPU. The server only needs the MLflow package + a Postgres driver;
# `mlflow server` resolves run artifacts via the artifacts-destination volume.
FROM python:3.12-slim@sha256:9c1d9ed7593f2552a4ea47362ec0d2ddf5923458a53d0c8e30edf8b398c94a31

# psycopg2-binary: Postgres backend-store driver. mlflow pinned to the 2.16 line, matching
# training/pyproject.toml's `train` group (mlflow>=2.15) so client/server stay compatible.
RUN pip install --no-cache-dir "mlflow>=2.16,<3" "psycopg2-binary>=2.9"

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Run as a non-root user (Trivy DS-0002, container-escape hardening — matches the Java service
# images which run as distroless UID 65532). Pre-create + own the artifacts dir so the named volume
# (atlas-mlflow-artifacts) inherits writable ownership on first creation. The server binds :5000
# (>1024), so no privileged port is needed.
RUN useradd --system --create-home --uid 10001 mlflow \
    && mkdir -p /mlflow/artifacts && chown -R mlflow:mlflow /mlflow
USER 10001

EXPOSE 5000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
