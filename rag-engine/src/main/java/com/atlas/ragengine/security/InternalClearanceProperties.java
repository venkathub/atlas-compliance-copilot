package com.atlas.ragengine.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Configuration for the Gateway→rag-engine internal verified-clearance assertion (ADR-0034 / D-P3-5).
 *
 * <p>On the Gateway-fronted path the Gateway is the trust boundary: it validates the client JWT and
 * re-asserts a verified clearance as a short-lived JWT signed with this shared secret. {@code rag-engine}
 * independently verifies it (defense-in-depth) and, when present, ignores any client-set
 * {@code X-Atlas-Clearance} shim header. Env-swappable; {@code rag-engine} holds the SAME value the
 * Gateway uses.
 *
 * @param internalSecret shared HMAC secret ({@code ATLAS_GATEWAY_INTERNAL_SECRET})
 */
@ConfigurationProperties(prefix = "atlas.gateway")
public record InternalClearanceProperties(String internalSecret) {

    public InternalClearanceProperties {
        internalSecret = (internalSecret == null || internalSecret.isBlank()) ? "change-me-locally" : internalSecret;
    }
}
