package com.atlas.ragengine.qa;

import java.util.UUID;

/**
 * One inline citation (ADR-0018, chunk-level). {@code marker} is the {@code [n]} number used in the
 * answer text; the rest is the source chunk's provenance for display/trace.
 */
public record Citation(
        int marker,
        UUID chunkId,
        UUID documentId,
        String docId,
        String title,
        String sourceUri,
        String clearance,
        double score,
        String snippet) {
}
