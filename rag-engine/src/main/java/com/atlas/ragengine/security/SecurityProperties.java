package com.atlas.ragengine.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * P1 clearance-transport shim configuration (ADR-0016) — <b>P1-only</b>, profile-gated to
 * {@code local}/{@code test}. Superseded by the simulated IdP in P3 (ADR-0003). Env-swappable.
 *
 * @param clearanceUsers    resource holding the D3 dev user→clearance map
 * @param headerUser        request header carrying the dev caller id
 * @param headerClearance   request header carrying an explicit clearance (wins over the user map)
 * @param defaultClearance  fallback clearance label when nothing resolves (fail-closed: public)
 */
@ConfigurationProperties(prefix = "atlas.security")
public record SecurityProperties(
        String clearanceUsers,
        String headerUser,
        String headerClearance,
        String defaultClearance) {

    public SecurityProperties {
        clearanceUsers = blankTo(clearanceUsers, "classpath:dev/clearance-users.json");
        headerUser = blankTo(headerUser, "X-Atlas-User");
        headerClearance = blankTo(headerClearance, "X-Atlas-Clearance");
        defaultClearance = blankTo(defaultClearance, "public");
    }

    private static String blankTo(String v, String fallback) {
        return (v == null || v.isBlank()) ? fallback : v;
    }

    public static SecurityProperties defaults() {
        return new SecurityProperties(null, null, null, null);
    }
}
