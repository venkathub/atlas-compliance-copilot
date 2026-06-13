package com.atlas.ragengine.ingest;

import java.util.Map;

/**
 * One loaded source document before chunking/embedding. Carries the content plus the
 * provenance/metadata needed for RBAC (clearance), integrity (sourceUri/origin), and
 * citations (title, metadata).
 *
 * @param docId        stable logical id (FinanceBench id or Layer-2 doc_id)
 * @param title        human title (for citations)
 * @param clearance    one of public|analyst|compliance|restricted (the RBAC key)
 * @param sourceUri    declared provenance URI (where the content came from)
 * @param sourceLayer  1 = RAG substrate (FinanceBench), 2 = AML overlay
 * @param origin       the classpath/file location it was actually read from (LLM04 allow-list)
 * @param content      the raw text to chunk + embed
 * @param metadata     extra citation/context metadata persisted onto each chunk
 */
public record SourceDocument(
        String docId,
        String title,
        String clearance,
        String sourceUri,
        int sourceLayer,
        String origin,
        String content,
        Map<String, Object> metadata) {
}
