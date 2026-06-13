package com.atlas.ragengine.retrieval;

import java.util.List;

/**
 * P1 reranker (ADR-0014): the RRF-fused order <em>is</em> the rerank — just truncate to {@code topK}.
 * The seam exists so a cross-encoder can replace this in P2 without changing callers.
 */
public class RrfPassThroughReranker implements Reranker {

    @Override
    public List<RetrievedChunk> rerank(String query, List<RetrievedChunk> fused, int topK) {
        if (topK <= 0 || topK >= fused.size()) {
            return fused;
        }
        return fused.subList(0, topK);
    }
}
