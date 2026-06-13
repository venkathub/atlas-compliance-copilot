package com.atlas.ragengine.retrieval;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Hybrid-retrieval tuning (env-swappable). Candidate depths per source and the RRF constant
 * (ADR-0013); {@code topK} is the default result size when a request omits it.
 *
 * @param denseK  dense (HNSW) candidate depth
 * @param sparseK sparse (tsvector) candidate depth
 * @param rrfK    RRF constant k (ADR-0013, default 60)
 * @param topK    default number of results after rerank/truncate
 */
@ConfigurationProperties(prefix = "atlas.retrieval")
public record RetrievalProperties(Integer denseK, Integer sparseK, Integer rrfK, Integer topK) {

    public RetrievalProperties {
        denseK = (denseK == null) ? 20 : denseK;
        sparseK = (sparseK == null) ? 20 : sparseK;
        rrfK = (rrfK == null) ? 60 : rrfK;
        topK = (topK == null) ? 6 : topK;
    }

    public static RetrievalProperties defaults() {
        return new RetrievalProperties(null, null, null, null);
    }
}
