package com.atlas.ragengine.ingest;

import com.atlas.ragengine.ingest.IngestionValidator.ValidationResult;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

/**
 * Orchestrates the ingestion pipeline as an <b>idempotent full rebuild</b>:
 * load → validate (LLM04) → chunk (ADR-0011) → embed + store. Re-running produces identical
 * rows (deterministic name-based UUIDs + TRUNCATE), so re-ingest is safe and repeatable.
 */
public class IngestionService {

    private static final Logger log = LoggerFactory.getLogger(IngestionService.class);

    private final CorpusLoader loader;
    private final IngestionValidator validator;
    private final DocumentChunker chunker;
    private final EmbeddingWriter writer;
    private final JdbcTemplate jdbc;

    public IngestionService(CorpusLoader loader, IngestionValidator validator,
            DocumentChunker chunker, EmbeddingWriter writer, JdbcTemplate jdbc) {
        this.loader = loader;
        this.validator = validator;
        this.chunker = chunker;
        this.writer = writer;
        this.jdbc = jdbc;
    }

    /** Outcome of a rebuild — surfaced by the admin ingest endpoint (P1 task 7). */
    public record IngestionReport(int documents, int chunks, int rejectedUntrusted) {
    }

    @Transactional
    public IngestionReport rebuild() {
        // Full rebuild: clear chunks + documents (chunk cascade-deletes with its document).
        jdbc.update("TRUNCATE TABLE atlas_document CASCADE");
        return ingest(loader.loadAll());
    }

    /**
     * Validate → chunk → embed → store the given documents, <b>without</b> truncating. Used by
     * {@link #rebuild()} and by tests that append documents (e.g. poisoned fixtures).
     */
    public IngestionReport ingest(List<SourceDocument> documents) {
        int docCount = 0;
        int chunks = 0;
        int rejected = 0;
        for (SourceDocument doc : documents) {
            ValidationResult vr = validator.validate(doc);
            if (!vr.accepted()) {
                rejected++;
                log.warn("Rejected document {} ({}): {}", doc.docId(), doc.origin(), vr.reason());
                continue;
            }
            UUID documentId = UUID.nameUUIDFromBytes(doc.docId().getBytes(StandardCharsets.UTF_8));
            jdbc.update(
                    "INSERT INTO atlas_document "
                            + "(id, source_uri, source_layer, title, clearance, content_sha256, trusted) "
                            + "VALUES (?, ?, ?, ?, ?, ?, TRUE)",
                    documentId, doc.sourceUri(), doc.sourceLayer(), doc.title(),
                    doc.clearance(), vr.contentSha256());

            List<DocumentChunker.Chunk> docChunks = chunker.chunk(doc.content());
            java.util.Map<String, Object> chunkMeta = new java.util.HashMap<>(doc.metadata());
            chunkMeta.put("docId", doc.docId());
            chunkMeta.put("title", doc.title());
            chunkMeta.put("sourceUri", doc.sourceUri());
            chunkMeta.put("sourceLayer", doc.sourceLayer());
            chunks += writer.write(documentId, doc.clearance(), chunkMeta, docChunks);
            docCount++;
        }
        IngestionReport report = new IngestionReport(docCount, chunks, rejected);
        log.info("Ingestion complete: {} documents, {} chunks, {} rejected (untrusted/invalid)",
                report.documents(), report.chunks(), report.rejectedUntrusted());
        return report;
    }
}
