package com.atlas.mcptools.audit;

/**
 * Lifecycle phase of a governed tool invocation, recorded in the append-only audit log
 * (P4_SPEC §2.3 / ADR-0048). Every invocation emits ≥1 row covering its lifecycle:
 * {@code ATTEMPT → APPROVED/REJECTED → SUCCESS/DENIED/ERROR}.
 */
public enum AuditPhase {
    /** The tool was invoked and validation is starting. */
    ATTEMPT,
    /** A human approval context was present and accepted. */
    APPROVED,
    /** The action was declined (no write performed). */
    REJECTED,
    /** The governed write completed (result_ref carries the draft reference). */
    SUCCESS,
    /** Authorization re-check failed (caller below the required clearance). */
    DENIED,
    /** The invocation failed unexpectedly (no partial write — transactional). */
    ERROR
}
