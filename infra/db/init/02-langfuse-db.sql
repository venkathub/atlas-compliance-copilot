-- Atlas P2 — create the `langfuse` database on the shared atlas-postgres instance.
-- Langfuse v3 reuses this Postgres (separate logical DB) for its relational store;
-- it runs its own Prisma migrations on first boot. ClickHouse + MinIO are separate
-- containers. Idempotent: only creates the DB if it does not already exist.
-- Applied by `make up` via `docker exec ... psql < this-file` (NOT a host bind mount —
-- see infra/README.md "Snap-Docker note").

SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

-- Echo so `make up` output proves the database exists.
SELECT datname AS langfuse_db FROM pg_database WHERE datname = 'langfuse';
