package com.atlas.ragengine.retrieval;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Hybrid-retrieval tuning (env-swappable). Candidate depths per source and the RRF constant
 * (ADR-0013); {@code topK} is the default result size when a request omits it.
 *
 * <p>{@code reranker} (rrf|llm) and {@code sparseQuery} (plainto|websearch) are the P2 eval-gated
 * knobs (ADR-0027 / D-P2-7): both default to the P1 behaviour and are flipped only if the harness
 * A/B proves a lift.
 *
 * @param denseK      dense (HNSW) candidate depth
 * @param sparseK     sparse (tsvector) candidate depth
 * @param rrfK        RRF constant k (ADR-0013, default 60)
 * @param topK        default number of results after rerank/truncate
 * @param reranker    {@code rrf} (default, pass-through) | {@code llm} (LLM-as-reranker)
 * @param sparseQuery {@code plainto} (default) | {@code websearch} (websearch_to_tsquery)
 */
@ConfigurationProperties(prefix = "atlas.retrieval")
public record RetrievalProperties(Integer denseK, Integer sparseK, Integer rrfK, Integer topK,
        String reranker, String sparseQuery) {

    public RetrievalProperties {
        denseK = (denseK == null) ? 20 : denseK;
        sparseK = (sparseK == null) ? 20 : sparseK;
        rrfK = (rrfK == null) ? 60 : rrfK;
        topK = (topK == null) ? 6 : topK;
        reranker = (reranker == null || reranker.isBlank()) ? "rrf" : reranker;
        sparseQuery = (sparseQuery == null || sparseQuery.isBlank()) ? "plainto" : sparseQuery;
    }

    public static RetrievalProperties defaults() {
        return new RetrievalProperties(null, null, null, null, null, null);
    }

    /** The Postgres FTS query function for the chosen sparse semantics (allow-listed, never raw). */
    public String tsqueryFunction() {
        return "websearch".equalsIgnoreCase(sparseQuery) ? "websearch_to_tsquery" : "plainto_tsquery";
    }

    public boolean llmReranker() {
        return "llm".equalsIgnoreCase(reranker);
    }
}
