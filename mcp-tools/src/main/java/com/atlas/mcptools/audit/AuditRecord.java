package com.atlas.mcptools.audit;

import java.time.Instant;

/**
 * An immutable {@code agent.tool_audit} row (ADR-0048). {@code seq} is the DB-assigned identity
 * (chain order); {@code ts} is set by the application so {@code row_hash} is reproducible.
 */
public record AuditRecord(
        long seq,
        Instant ts,
        String runId,
        String tool,
        AuditPhase phase,
        String caller,
        String clearance,
        String argsDigest,
        String resultRef,
        String prevHash,
        String rowHash) {
}
