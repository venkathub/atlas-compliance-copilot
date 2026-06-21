package com.atlas.mcptools.auth;

import java.util.Locale;

/**
 * The Atlas clearance hierarchy as seen by the MCP tool server (mirrors the rag-engine/gateway core,
 * ADR-0012). mcp-tools owns its own copy (ADR-0001 — modules never import one another). Strictly
 * ordered {@code PUBLIC(0) < ANALYST(1) < COMPLIANCE(2) < RESTRICTED(3)}; the wire form is the
 * lowercase {@link #label()} carried in the JWT {@code clearance} claim.
 */
public enum Clearance {

    PUBLIC(0),
    ANALYST(1),
    COMPLIANCE(2),
    RESTRICTED(3);

    private final int rank;

    Clearance(int rank) {
        this.rank = rank;
    }

    public int rank() {
        return rank;
    }

    public String label() {
        return name().toLowerCase(Locale.ROOT);
    }

    /** True if this clearance is at least {@code other} in the hierarchy. */
    public boolean atLeast(Clearance other) {
        return this.rank >= other.rank;
    }

    /** Parse a clearance label (case-insensitive); throws {@link IllegalArgumentException} if unknown. */
    public static Clearance fromLabel(String label) {
        if (label == null) {
            throw new IllegalArgumentException("clearance label is null");
        }
        return Clearance.valueOf(label.strip().toUpperCase(Locale.ROOT));
    }
}
