package com.atlas.gateway.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Gateway downstream configuration: where {@code rag-engine} lives and the shared secret used to
 * sign the internal-hop verified-clearance assertion (ADR-0034 / D-P3-5). Env-swappable.
 *
 * @param ragEngineUrl   base URL of the downstream RAG Engine ({@code ATLAS_GATEWAY_RAG_ENGINE_URL})
 * @param internalSecret HMAC secret for the Gateway→rag-engine internal clearance assertion
 *                       ({@code ATLAS_GATEWAY_INTERNAL_SECRET}); rag-engine holds the same value
 */
@ConfigurationProperties(prefix = "atlas.gateway")
public record GatewayProperties(String ragEngineUrl, String internalSecret) {

    public GatewayProperties {
        ragEngineUrl = blankTo(ragEngineUrl, "http://localhost:8081");
        internalSecret = blankTo(internalSecret, "change-me-locally");
    }

    private static String blankTo(String v, String fallback) {
        return (v == null || v.isBlank()) ? fallback : v;
    }
}
