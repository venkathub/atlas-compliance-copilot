-- Atlas P0 — enable pgvector + text-search helpers.
-- Idempotent. Applied by `make up` via `docker exec ... psql < this-file`
-- (NOT a host bind mount — see infra/README.md "Snap-Docker note").

CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector: dense embeddings (HNSW in P1)
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- trigram support for hybrid/keyword search

-- Echo versions so `make up` output proves the extensions loaded.
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_trgm') ORDER BY extname;
