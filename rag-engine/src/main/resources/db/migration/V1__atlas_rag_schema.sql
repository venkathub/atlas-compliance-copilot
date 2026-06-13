-- Atlas P1 — permission-aware RAG schema (pgvector, PostgreSQL 16).
--
-- Two tables: a document (provenance) table and a chunk (embedding) table.
-- Per P1_SPEC §2.3 and ADR-0002 (pgvector+HNSW+hybrid) / ADR-0005 (768-dim embeddings)
-- / ADR-0012 (hierarchical clearance enforced as a single SQL predicate).
--
-- NOTE: we use a CUSTOM schema (not Spring AI's stock `vector_store` table) because the
-- hybrid sparse `tsvector` column + the hard RBAC `clearance` predicate are not expressible
-- through the stock PgVectorStore alone (see P1_SPEC §2.3 note).
--
-- The `vector(768)` dimension is fixed by ADR-0005 (nomic-embed-text) and must stay in sync
-- with `EMBED_DIM` in .env. Flyway SQL cannot interpolate env vars, so 768 is hardcoded here
-- as the single source of truth; changing the embed model requires a re-embed migration.

-- pgvector extension. infra/db/init/01-extensions.sql also creates this for the local stack,
-- but Testcontainers boots a bare pgvector image without that init step, so we (idempotently)
-- ensure it here too.
CREATE EXTENSION IF NOT EXISTS vector;

-- documents: one row per source document (provenance / OWASP LLM04 integrity).
CREATE TABLE atlas_document (
    id             UUID PRIMARY KEY,
    source_uri     TEXT NOT NULL,             -- where it came from (file path / EDGAR url)
    source_layer   SMALLINT NOT NULL,         -- 1 = RAG substrate, 2 = AML overlay
    title          TEXT,
    clearance      TEXT NOT NULL,             -- public|analyst|compliance|restricted
    content_sha256 TEXT NOT NULL,             -- integrity (LLM04)
    trusted        BOOLEAN NOT NULL DEFAULT TRUE,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT atlas_document_clearance_chk
        CHECK (clearance IN ('public', 'analyst', 'compliance', 'restricted'))
);

-- chunks: the retrieval unit. clearance is denormalized onto the chunk so the RBAC filter
-- is a single indexed predicate on this table (no join needed in the hot retrieval path).
CREATE TABLE atlas_chunk (
    id           UUID PRIMARY KEY,
    document_id  UUID NOT NULL REFERENCES atlas_document(id) ON DELETE CASCADE,
    chunk_index  INT  NOT NULL,
    content      TEXT NOT NULL,
    clearance    TEXT NOT NULL,               -- inherited from document; the RBAC key
    metadata     JSONB NOT NULL DEFAULT '{}', -- title, page, section, source_uri (for citations)
    embedding    vector(768) NOT NULL,        -- dense embedding (ADR-0005)
    content_tsv  tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    CONSTRAINT atlas_chunk_clearance_chk
        CHECK (clearance IN ('public', 'analyst', 'compliance', 'restricted')),
    CONSTRAINT atlas_chunk_doc_idx_uq UNIQUE (document_id, chunk_index)
);

-- Dense kNN (cosine) — HNSW index for the dense retrieval path.
CREATE INDEX atlas_chunk_hnsw  ON atlas_chunk USING hnsw (embedding vector_cosine_ops);
-- Sparse full-text — GIN index for the keyword/tsvector retrieval path.
CREATE INDEX atlas_chunk_tsv   ON atlas_chunk USING gin (content_tsv);
-- RBAC pre-filter — btree on clearance so the `clearance <= caller` predicate is cheap.
CREATE INDEX atlas_chunk_clear ON atlas_chunk (clearance);
