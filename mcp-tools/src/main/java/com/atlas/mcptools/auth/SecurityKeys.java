package com.atlas.mcptools.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Derives a fixed-length HMAC key from a configured secret of any length (HS256 needs ≥ 256 bits).
 *
 * <p>{@code SHA-256(secret)} → 32 bytes. mcp-tools owns its own copy on purpose (modules never import
 * one another — ADR-0001); it MUST match the sim-IdP's derivation (gateway {@code SecurityKeys}) so the
 * resource server can verify tokens the sim-IdP mints (ADR-0046, task 5).
 */
public final class SecurityKeys {

    private SecurityKeys() {}

    /** {@code SHA-256(secret)} → a 32-byte (256-bit) key suitable for HS256. */
    public static byte[] deriveHs256(String secret) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalArgumentException("HMAC secret must not be blank");
        }
        try {
            return MessageDigest.getInstance("SHA-256").digest(secret.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
