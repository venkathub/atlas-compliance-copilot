package com.atlas.ragengine.retrieval;

import java.util.List;

/**
 * Reranking seam (ADR-0014). P1 ships {@link RrfPassThroughReranker} — the RRF-fused order, truncated
 * to {@code topK} — keeping the focus on RBAC correctness. A cross-encoder reranker drops in behind
 * this interface in P2 (where evals can prove it earns its cost) with no caller changes.
 */
public interface Reranker {

    List<RetrievedChunk> rerank(String query, List<RetrievedChunk> fused, int topK);
}
