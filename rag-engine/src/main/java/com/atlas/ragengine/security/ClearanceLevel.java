package com.atlas.ragengine.security;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * The Atlas clearance hierarchy — the RBAC core (ADR-0012).
 *
 * <p>Strictly ordered: {@code PUBLIC(0) < ANALYST(1) < COMPLIANCE(2) < RESTRICTED(3)}. A caller at
 * level <em>L</em> may see content at any level ≤ <em>L</em> (hierarchical, not set-membership).
 * The persisted/DB form is the lowercase {@link #label()} (matches the {@code clearance} CHECK
 * constraint and the corpus front-matter).
 */
public enum ClearanceLevel {

    PUBLIC(0),
    ANALYST(1),
    COMPLIANCE(2),
    RESTRICTED(3);

    private final int rank;

    ClearanceLevel(int rank) {
        this.rank = rank;
    }

    public int rank() {
        return rank;
    }

    /** Lowercase persisted/DB label (e.g. {@code "compliance"}). */
    public String label() {
        return name().toLowerCase(Locale.ROOT);
    }

    /** True if this level is allowed to see {@code other} (i.e. {@code other <= this}). */
    public boolean dominates(ClearanceLevel other) {
        return other.rank <= this.rank;
    }

    /** The set of levels a caller at this clearance may see — itself and everything below. */
    public List<ClearanceLevel> atOrBelow() {
        return Arrays.stream(values()).filter(this::dominates).toList();
    }

    /** Labels of {@link #atOrBelow()} — the values used in the RBAC SQL predicate. */
    public List<String> visibleLabels() {
        return atOrBelow().stream().map(ClearanceLevel::label).toList();
    }

    /**
     * Parse a clearance label (case-insensitive). Throws {@link IllegalArgumentException} for any
     * unknown value — callers that must fail closed should catch and deny.
     */
    public static ClearanceLevel fromLabel(String label) {
        if (label == null) {
            throw new IllegalArgumentException("clearance label is null");
        }
        return ClearanceLevel.valueOf(label.strip().toUpperCase(Locale.ROOT));
    }
}
