package com.atlas.ragengine.observability;

/**
 * Trace content-capture policy (ADR-0030 / D-P2-10). {@code OFF} = metadata only (ids, clearance,
 * model, token counts, latencies — never chunk text or PII); {@code FULL} = redaction-filtered
 * prompt/response content, LOCAL DEV ONLY (never a shared/prod stack).
 */
public enum ContentMode {
    OFF,
    FULL;

    public static ContentMode fromValue(String value) {
        if (value == null) {
            return OFF;
        }
        return "full".equalsIgnoreCase(value.trim()) ? FULL : OFF;
    }
}
