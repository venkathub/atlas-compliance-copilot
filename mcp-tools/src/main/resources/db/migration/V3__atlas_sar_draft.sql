-- Atlas P4 — draft-SAR write target (PostgreSQL 16, `agent` schema).
--
-- Per P4_SPEC §2.3 and ADR-0049 (governed transactional write to a sar_draft table, status DRAFT,
-- links citations + run_id, returned for human review). Unlike tool_audit (V2), sar_draft is NOT
-- append-only: a draft is a mutable working artifact (P5 may advance its status / render it), so no
-- mutation trigger is installed here.
--
-- The write is performed by the least-privilege runtime role `atlas_mcp_app` (created in V2); it gets
-- INSERT + SELECT on the table and USAGE on the draft-ref sequence.

-- Monotonic source for the human-facing draft reference (SAR-<year>-<6 digits>). nextval is
-- non-transactional (gaps on rollback are acceptable for a reference number).
CREATE SEQUENCE agent.sar_draft_ref_seq;

CREATE TABLE agent.sar_draft (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    draft_ref  TEXT UNIQUE NOT NULL,                 -- e.g. SAR-2026-000123
    account    TEXT NOT NULL,
    period     TEXT NOT NULL,                        -- ^[0-9]{4}-Q[1-4]$ (validated in the tool)
    rationale  TEXT NOT NULL,
    citations  JSONB NOT NULL,                       -- source doc refs (grounding / provenance)
    clearance  TEXT NOT NULL,                        -- caller clearance at write time (must be compliance+)
    run_id     TEXT NOT NULL,                        -- originating agent run
    status     TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX sar_draft_account_idx ON agent.sar_draft (account, period);
CREATE INDEX sar_draft_run_id_idx ON agent.sar_draft (run_id);

GRANT INSERT, SELECT ON agent.sar_draft TO atlas_mcp_app;
GRANT USAGE ON SEQUENCE agent.sar_draft_ref_seq TO atlas_mcp_app;
