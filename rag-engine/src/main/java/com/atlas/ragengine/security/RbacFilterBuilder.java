package com.atlas.ragengine.security;

/**
 * Builds the mandatory RBAC predicate enforced at retrieval time (ADR-0012). Centralizing it here
 * means every retrieval path (dense kNN and sparse tsvector) shares one trust boundary that cannot
 * be bypassed — the predicate is pushed into SQL, never applied as an optional post-filter.
 *
 * <p>Encoding: {@code clearance = ANY(?)} bound to the array of the caller's visible labels (e.g.
 * caller=COMPLIANCE → {@code {public, analyst, compliance}}). This is semantically {@code level <=
 * caller} but is index-friendly on {@code atlas_chunk_clear} and fully parameterized (no SQL string
 * interpolation of caller input).
 */
public class RbacFilterBuilder {

    /** A reusable SQL predicate fragment plus its bound parameters. */
    public record RbacPredicate(String sqlFragment, Object[] params) {
    }

    /**
     * The RBAC predicate for a caller, against the given column.
     *
     * @param clearanceColumn the chunk clearance column (e.g. {@code "clearance"} or {@code "c.clearance"})
     * @param caller          the caller's clearance level
     */
    public RbacPredicate predicate(String clearanceColumn, ClearanceLevel caller) {
        if (clearanceColumn == null || clearanceColumn.isBlank()) {
            throw new IllegalArgumentException("clearanceColumn required");
        }
        String[] visible = caller.visibleLabels().toArray(String[]::new);
        return new RbacPredicate(clearanceColumn + " = ANY(?)", new Object[] {visible});
    }

    /**
     * Defense-in-depth check (ADR-0012): a returned chunk/citation at {@code itemClearance} must be
     * visible to {@code caller}. The controller re-asserts this on every result so a retrieval bug
     * can never surface above-clearance content.
     *
     * @return true if visible (allowed); false if it exceeds the caller's clearance (a leak)
     */
    public boolean isVisible(ClearanceLevel caller, ClearanceLevel itemClearance) {
        return caller.dominates(itemClearance);
    }

    /** Convenience overload accepting the persisted label; unknown labels fail closed (not visible). */
    public boolean isVisible(ClearanceLevel caller, String itemClearanceLabel) {
        try {
            return isVisible(caller, ClearanceLevel.fromLabel(itemClearanceLabel));
        } catch (IllegalArgumentException e) {
            return false;
        }
    }
}
