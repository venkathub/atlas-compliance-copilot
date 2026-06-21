package com.atlas.gateway.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Resource-scoped (RFC 8707) token config for the MCP hop (ADR-0046, P4 task 5). Kept separate from
 * {@link IdpProperties} so this is a purely additive change to the frozen sim-IdP — the signing key and
 * issuer are reused from {@link IdpProperties}; only the audience + short TTL are new.
 *
 * @param audience   the {@code aud} (RFC 8707 resource indicator) naming the MCP tool server
 *                   ({@code ATLAS_IDP_RESOURCE_AUDIENCE})
 * @param ttlSeconds short lifetime for a resource-scoped token ({@code ATLAS_IDP_RESOURCE_TOKEN_TTL_SECONDS})
 */
@ConfigurationProperties(prefix = "atlas.idp.resource")
public record ResourceTokenProperties(String audience, long ttlSeconds) {

    public ResourceTokenProperties {
        audience = (audience == null || audience.isBlank()) ? "atlas-mcp-tools" : audience;
        ttlSeconds = ttlSeconds > 0 ? ttlSeconds : 300L;
    }
}
