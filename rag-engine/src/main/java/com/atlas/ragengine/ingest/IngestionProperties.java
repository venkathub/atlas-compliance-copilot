package com.atlas.ragengine.ingest;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Ingestion configuration — all env-swappable (CLAUDE.md: no hardcoded paths/sizes).
 *
 * @param layer1Manifest  classpath/file location of the Layer-1 FinanceBench manifest
 * @param layer2Glob      resource glob for the Layer-2 authored overlay markdown
 * @param chunkSize       target chunk size in (estimated) tokens (ADR-0011)
 * @param chunkOverlap    overlap between consecutive chunks in (estimated) tokens (ADR-0011)
 * @param embeddingDim    embedding dimension; must match the pgvector column (ADR-0005, 768)
 * @param trustedOrigins  LLM04 allow-list: a document is admitted only if its origin starts
 *                        with one of these prefixes (trusted-corpus-only admission)
 */
@ConfigurationProperties(prefix = "atlas.ingest")
public record IngestionProperties(
        String layer1Manifest,
        String layer2Glob,
        Integer chunkSize,
        Integer chunkOverlap,
        Integer embeddingDim,
        List<String> trustedOrigins) {

    public IngestionProperties {
        layer1Manifest = (layer1Manifest == null || layer1Manifest.isBlank())
                ? "classpath:corpus/layer1/manifest.json" : layer1Manifest;
        layer2Glob = (layer2Glob == null || layer2Glob.isBlank())
                ? "classpath:corpus/layer2/*.md" : layer2Glob;
        chunkSize = (chunkSize == null) ? 512 : chunkSize;
        chunkOverlap = (chunkOverlap == null) ? 64 : chunkOverlap;
        embeddingDim = (embeddingDim == null) ? 768 : embeddingDim;
        trustedOrigins = (trustedOrigins == null || trustedOrigins.isEmpty())
                ? List.of("classpath:corpus/", "classpath:/corpus/") : List.copyOf(trustedOrigins);
    }

    /** Defaults suitable for tests / direct wiring. */
    public static IngestionProperties defaults() {
        return new IngestionProperties(null, null, null, null, null, null);
    }
}
