package com.atlas.mcptools.audit;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Small SHA-256 helper. Used for the audit hash chain and for args digests (no raw PII; LLM02). */
public final class Digests {

    private Digests() {}

    /** Lowercase hex SHA-256 of the UTF-8 bytes of {@code input}. */
    public static String sha256Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 is mandated by the JLS spec for every JVM — unreachable.
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
