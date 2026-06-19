package com.atlas.gateway.auth;

import java.util.Locale;

/**
 * The Atlas clearance hierarchy as seen by the Gateway (mirrors the rag-engine RBAC core, ADR-0012).
 *
 * <p>The Gateway owns its own copy on purpose: per P3_SPEC §2.1 the Gateway and {@code rag-engine}
 * never import each other (a clean seam the P4 agents will also sit behind). Strictly ordered
 * {@code PUBLIC(0) < ANALYST(1) < COMPLIANCE(2) < RESTRICTED(3)}; the wire form is the lowercase
 * {@link #label()} used in the JWT {@code clearance} claim.
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

    /** Lowercase wire/label form (e.g. {@code "compliance"}). */
    public String label() {
        return name().toLowerCase(Locale.ROOT);
    }

    /** Parse a clearance label (case-insensitive); throws {@link IllegalArgumentException} if unknown. */
    public static Clearance fromLabel(String label) {
        if (label == null) {
            throw new IllegalArgumentException("clearance label is null");
        }
        return Clearance.valueOf(label.strip().toUpperCase(Locale.ROOT));
    }
}
