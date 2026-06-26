package com.atlas.mcptools.audit;

import java.time.Instant;

/**
 * A read-only, admin-facing projection of an {@code agent.tool_audit} row (P5 Task 5). Deliberately
 * omits {@code args_digest} and the hash-chain columns — the audit view shows refs/digests, never raw
 * PII (LLM02). Jackson serializes these record components verbatim (camelCase wire).
 */
public record AuditRowView(
        long seq,
        Instant ts,
        String runId,
        String tool,
        String phase,
        String caller,
        String clearance,
        String resultRef) {
}
