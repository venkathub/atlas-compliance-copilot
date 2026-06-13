package com.atlas.ragengine.retrieval;

import java.util.Map;
import java.util.UUID;

/**
 * One chunk returned from retrieval, with enough provenance for RBAC re-checks, fusion, and
 * citations.
 *
 * @param id          chunk id
 * @param documentId  owning document id
 * @param content     chunk text
 * @param clearance   chunk clearance label (the RBAC key — re-checked defense-in-depth)
 * @param metadata    chunk metadata (docId, title, sourceUri, …) for citations + D4 assertions
 * @param score       fused/rerank score (higher = more relevant)
 */
public record RetrievedChunk(
        UUID id,
        UUID documentId,
        String content,
        String clearance,
        Map<String, Object> metadata,
        double score) {

    public String docId() {
        Object v = metadata.get("docId");
        return v == null ? null : v.toString();
    }

    public String title() {
        Object v = metadata.get("title");
        return v == null ? null : v.toString();
    }

    public String sourceUri() {
        Object v = metadata.get("sourceUri");
        return v == null ? null : v.toString();
    }

    /** Copy with a replaced score (used by fusion/rerank). */
    public RetrievedChunk withScore(double newScore) {
        return new RetrievedChunk(id, documentId, content, clearance, metadata, newScore);
    }
}
