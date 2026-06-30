-- Atlas P6 — create the `mlflow` database on the shared atlas-postgres instance.
-- MLflow (tracking + model registry) reuses this Postgres (separate logical DB) for its
-- run/registry METADATA only (ADR-0072). The durable artifact store is the Hugging Face
-- Hub: the fine-tuned adapter is pushed to HF pre-GPU-teardown and the registry version
-- records the HF repo+revision as its source, so the model survives GPU teardown.
-- MLflow runs its own schema migrations on first server boot. Idempotent: only creates
-- the DB if it does not already exist.
-- Applied by `make up` via `docker exec ... psql < this-file` (NOT a host bind mount —
-- see infra/README.md "Snap-Docker note").

SELECT 'CREATE DATABASE mlflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec

-- Echo so `make up` output proves the database exists.
SELECT datname AS mlflow_db FROM pg_database WHERE datname = 'mlflow';
