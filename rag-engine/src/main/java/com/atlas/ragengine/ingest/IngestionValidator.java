package com.atlas.ragengine.ingest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;

/**
 * Ingestion integrity gate (OWASP <b>LLM04</b>): admits only trusted-corpus documents and records
 * a content hash for provenance.
 * <ul>
 *   <li><b>Trusted-source allow-list:</b> a document is admitted only if its {@code origin} starts
 *       with one of the configured trusted prefixes — untrusted sources are rejected, never stored.</li>
 *   <li><b>Content integrity:</b> a SHA-256 of the content is recorded on the document row.</li>
 *   <li><b>Clearance sanity:</b> clearance must be one of the four known levels (the DB CHECK
 *       constraint is the backstop; this gives a clean ingest-time error).</li>
 * </ul>
 */
public class IngestionValidator {

    static final Set<String> VALID_CLEARANCES = Set.of("public", "analyst", "compliance", "restricted");

    private final List<String> trustedOrigins;

    public IngestionValidator(List<String> trustedOrigins) {
        this.trustedOrigins = List.copyOf(trustedOrigins);
    }

    /** Result of validating one source document. */
    public record ValidationResult(boolean accepted, String reason, String contentSha256) {
        static ValidationResult rejected(String reason) {
            return new ValidationResult(false, reason, null);
        }
    }

    public ValidationResult validate(SourceDocument doc) {
        if (doc.origin() == null || trustedOrigins.stream().noneMatch(doc.origin()::startsWith)) {
            return ValidationResult.rejected("untrusted-source: " + doc.origin());
        }
        if (doc.clearance() == null || !VALID_CLEARANCES.contains(doc.clearance())) {
            return ValidationResult.rejected("invalid-clearance: " + doc.clearance());
        }
        if (doc.content() == null || doc.content().isBlank()) {
            return ValidationResult.rejected("empty-content: " + doc.docId());
        }
        return new ValidationResult(true, "ok", sha256(doc.content()));
    }

    /** Lowercase hex SHA-256 of the UTF-8 content. */
    public static String sha256(String content) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(md.digest(content.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }
}
