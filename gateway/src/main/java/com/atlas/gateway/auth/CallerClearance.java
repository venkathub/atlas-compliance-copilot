package com.atlas.gateway.auth;

/**
 * The verified caller identity resolved by {@link JwtClearanceFilter} from a valid client JWT.
 * Stored as a request attribute under {@link #ATTRIBUTE} for the query path (P3 task 3) to read.
 *
 * @param subject the {@code sub} claim (dev user id)
 * @param clearance the verified clearance the Gateway will re-assert to {@code rag-engine}
 */
public record CallerClearance(String subject, Clearance clearance) {

    /** Request-attribute key under which the filter stashes the resolved caller. */
    public static final String ATTRIBUTE = "atlas.caller";
}
