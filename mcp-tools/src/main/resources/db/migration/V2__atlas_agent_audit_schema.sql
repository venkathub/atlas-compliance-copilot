-- Atlas P4 — governed-action audit schema (PostgreSQL 16, `agent` schema).
--
-- Per P4_SPEC §2.3 and ADR-0048 (append-only, hash-chained, tamper-evident audit log) /
-- ADR-0047 (dedicated `agent` schema, isolated from rag-engine's public schema).
--
-- This migration is intentionally run by a PRIVILEGED role (spring.flyway.user, e.g. `atlas`),
-- while the application connects at runtime as the least-privilege role `atlas_mcp_app`
-- (spring.datasource.username). Two independent append-only protections are installed:
--   1. GRANT model — atlas_mcp_app gets INSERT + SELECT only; UPDATE/DELETE are revoked.
--   2. Trigger guard — BEFORE UPDATE/DELETE raises, which holds even against the table OWNER
--      (a Postgres owner keeps UPDATE/DELETE regardless of REVOKE), making the log truly
--      append-only at the DB layer. Tamper-evidence is provided by the hash chain (verifier).
--
-- The file is named V2 (P4_SPEC §2.2) to reflect the shared-DB lineage (rag-engine owns V1 in
-- `public`); mcp-tools keeps its OWN Flyway history table in the `agent` schema, so the numbering
-- is cosmetic and never collides with rag-engine's history.
--
-- ${app_password} is a Flyway placeholder bound from ATLAS_MCP_DB_APP_PASSWORD (never hardcoded).

CREATE SCHEMA IF NOT EXISTS agent;

-- ── tool_audit: append-only, hash-chained record of every governed tool invocation ──────────
CREATE TABLE agent.tool_audit (
    seq         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL,                 -- set by the app so the row_hash is reproducible
    run_id      TEXT NOT NULL,                        -- originating agent run
    tool        TEXT NOT NULL,                        -- e.g. open_draft_sar
    phase       TEXT NOT NULL,                        -- ATTEMPT|APPROVED|REJECTED|SUCCESS|DENIED|ERROR
    caller      TEXT NOT NULL,                        -- subject from the validated token
    clearance   TEXT NOT NULL,                        -- caller clearance at invocation time
    args_digest TEXT NOT NULL,                        -- sha256 of canonical args (no raw PII; LLM02)
    result_ref  TEXT,                                 -- draft_ref on SUCCESS (nullable)
    prev_hash   TEXT NOT NULL,                        -- chain link (prior row_hash; genesis = 64×'0')
    row_hash    TEXT NOT NULL,                        -- sha256(prev_hash || canonical(row fields))
    CONSTRAINT tool_audit_phase_chk
        CHECK (phase IN ('ATTEMPT', 'APPROVED', 'REJECTED', 'SUCCESS', 'DENIED', 'ERROR'))
);

-- Queryable for compliance review (P4_SPEC §2.4): by run_id (and caller/tool).
CREATE INDEX tool_audit_run_id_idx ON agent.tool_audit (run_id);
CREATE INDEX tool_audit_caller_idx ON agent.tool_audit (caller);

-- ── Append-only trigger guard (owner-proof) ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION agent.tool_audit_no_mutate() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'agent.tool_audit is append-only (% rejected)', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tool_audit_append_only
    BEFORE UPDATE OR DELETE ON agent.tool_audit
    FOR EACH ROW EXECUTE FUNCTION agent.tool_audit_no_mutate();

-- ── Least-privilege application role ────────────────────────────────────────────────────────
-- Created idempotently so re-running against a shared DB is safe. Password comes from an env-bound
-- Flyway placeholder. In real prod the role is provisioned out-of-band; here we create it so dev,
-- Docker Compose, and Testcontainers all behave identically.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_mcp_app') THEN
        CREATE ROLE atlas_mcp_app LOGIN PASSWORD '${app_password}';
    ELSE
        ALTER ROLE atlas_mcp_app LOGIN PASSWORD '${app_password}';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA agent TO atlas_mcp_app;
GRANT INSERT, SELECT ON agent.tool_audit TO atlas_mcp_app;
REVOKE UPDATE, DELETE ON agent.tool_audit FROM atlas_mcp_app;
