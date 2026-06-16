package com.atlas.gateway.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Simulated-IdP configuration (ADR-0034, realizes ADR-0003). Env-swappable, never hardcoded.
 *
 * @param signingKey      HMAC secret for the client-facing clearance JWT ({@code ATLAS_IDP_SIGNING_KEY})
 * @param issuer          the {@code iss} claim the Gateway mints and validates ({@code ATLAS_IDP_ISSUER})
 * @param tokenTtlSeconds client-token lifetime ({@code ATLAS_IDP_TOKEN_TTL_SECONDS})
 * @param devUsers        resource holding the simulated user→clearance directory
 */
@ConfigurationProperties(prefix = "atlas.idp")
public record IdpProperties(
        String signingKey,
        String issuer,
        long tokenTtlSeconds,
        String devUsers) {

    public IdpProperties {
        signingKey = blankTo(signingKey, "change-me-locally");
        issuer = blankTo(issuer, "atlas-sim-idp");
        tokenTtlSeconds = tokenTtlSeconds > 0 ? tokenTtlSeconds : 3600L;
        devUsers = blankTo(devUsers, "classpath:dev/clearance-users.json");
    }

    private static String blankTo(String v, String fallback) {
        return (v == null || v.isBlank()) ? fallback : v;
    }
}
