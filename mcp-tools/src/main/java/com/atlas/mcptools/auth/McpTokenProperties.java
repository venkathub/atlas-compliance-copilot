package com.atlas.mcptools.auth;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * OAuth 2.1 resource-server config for the MCP tool server (ADR-0046). All env-swappable.
 *
 * @param signingKey       HMAC secret shared with the sim-IdP (gateway); HS256 key = SHA-256(secret)
 * @param issuer           expected token {@code iss} (the sim-IdP)
 * @param audience         expected token {@code aud} (RFC 8707 resource indicator = this server)
 * @param requiredClearance minimum clearance the tool will act for (per-call re-check, LLM06)
 */
@ConfigurationProperties(prefix = "atlas.mcp.token")
public record McpTokenProperties(
        String signingKey,
        String issuer,
        String audience,
        String requiredClearance) {

    public McpTokenProperties {
        issuer = (issuer == null || issuer.isBlank()) ? "atlas-sim-idp" : issuer;
        audience = (audience == null || audience.isBlank()) ? "atlas-mcp-tools" : audience;
        requiredClearance = (requiredClearance == null || requiredClearance.isBlank())
                ? "compliance" : requiredClearance;
    }
}
