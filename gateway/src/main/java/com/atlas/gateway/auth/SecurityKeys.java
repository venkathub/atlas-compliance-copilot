package com.atlas.gateway.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Derives a fixed-length HMAC key from a configured secret of any length.
 *
 * <p>HS256 requires a key of at least 256 bits. Operator secrets are often shorter, human-readable
 * strings (e.g. the {@code .env.example} {@code change-me-locally} placeholder), so we deterministically
 * derive a 256-bit key as {@code SHA-256(secret)}. A proper {@code openssl rand -base64 32} secret also
 * works (it is simply re-hashed). The Gateway (signer) and {@code rag-engine} (verifier) MUST use this
 * identical derivation for the internal-hop assertion to verify (ADR-0034 / D-P3-5).
 */
public final class SecurityKeys {

    private SecurityKeys() {
    }

    /** {@code SHA-256(secret)} → a 32-byte (256-bit) key suitable for HS256. */
    public static byte[] deriveHs256(String secret) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalArgumentException("HMAC secret must not be blank");
        }
        try {
            return MessageDigest.getInstance("SHA-256").digest(secret.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e); // never on a standard JRE
        }
    }
}
