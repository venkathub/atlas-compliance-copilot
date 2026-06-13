package com.atlas.ragengine.retrieval;

import com.atlas.ragengine.security.ClearanceLevel;
import java.util.List;

/**
 * Permission-aware hybrid retriever: dense (HNSW) + sparse (tsvector) candidate generation — both
 * with the mandatory RBAC predicate pushed into SQL (ADR-0012) — fused with RRF (ADR-0013) and
 * reranked/truncated (ADR-0014). The single entry point used by the QA layer (task 7).
 */
public class HybridDocumentRetriever {

    private final DenseRetriever denseRetriever;
    private final SparseRetriever sparseRetriever;
    private final ReciprocalRankFusion fusion;
    private final Reranker reranker;
    private final RetrievalProperties props;

    public HybridDocumentRetriever(DenseRetriever denseRetriever, SparseRetriever sparseRetriever,
            ReciprocalRankFusion fusion, Reranker reranker, RetrievalProperties props) {
        this.denseRetriever = denseRetriever;
        this.sparseRetriever = sparseRetriever;
        this.fusion = fusion;
        this.reranker = reranker;
        this.props = props;
    }

    /** Retrieval stats surfaced alongside the answer (the visible "trace"). */
    public record RetrievalStats(int denseHits, int sparseHits, int fused, int reranked,
            String clearanceApplied) {
    }

    /** Hybrid result: the reranked chunks (already RBAC-filtered) plus retrieval stats. */
    public record RetrievalResult(List<RetrievedChunk> chunks, RetrievalStats stats) {
    }

    public RetrievalResult retrieve(String query, ClearanceLevel caller, int topK) {
        int effectiveTopK = topK > 0 ? topK : props.topK();
        List<RetrievedChunk> dense = denseRetriever.retrieve(query, caller, props.denseK());
        List<RetrievedChunk> sparse = sparseRetriever.retrieve(query, caller, props.sparseK());
        List<RetrievedChunk> fused = fusion.fuse(List.of(dense, sparse));
        List<RetrievedChunk> reranked = reranker.rerank(query, fused, effectiveTopK);
        RetrievalStats stats = new RetrievalStats(
                dense.size(), sparse.size(), fused.size(), reranked.size(), caller.label());
        return new RetrievalResult(reranked, stats);
    }
}
