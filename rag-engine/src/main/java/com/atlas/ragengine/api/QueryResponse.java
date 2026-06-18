package com.atlas.ragengine.api;

import com.atlas.ragengine.qa.Citation;
import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;

/**
 * {@code POST /v1/query} response — the §2.4 contract: answer + citations + retrieval trace, plus the
 * opt-in {@code contexts} (ADR-0023 / D-P2-3) when {@code includeContexts=true}. {@code contexts} is
 * omitted (null) for normal callers so the default contract is unchanged.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record QueryResponse(String answer, List<Citation> citations, RetrievalTrace retrieval,
        List<ContextChunk> contexts, TokenUsage usage) {

    /** The visible retrieval trace surfaced to the caller/UI. */
    public record RetrievalTrace(int denseHits, int sparseHits, int fused, int reranked,
            String clearanceApplied) {
        static RetrievalTrace from(RetrievalStats s) {
            return new RetrievalTrace(s.denseHits(), s.sparseHits(), s.fused(), s.reranked(),
                    s.clearanceApplied());
        }
    }

    /** Token usage for the model call (P3, ADR-0040) — the gateway uses it for real cost accounting. */
    public record TokenUsage(Integer promptTokens, Integer completionTokens) {
        static TokenUsage from(QaResult.TokenUsage u) {
            return u == null ? null : new TokenUsage(u.promptTokens(), u.completionTokens());
        }
    }

    /**
     * One full retrieved context chunk the model saw (eval-harness view). RBAC-filtered: it can only
     * contain chunks {@code <=} caller clearance — exposing <em>what the model saw</em>, never above it.
     */
    public record ContextChunk(String chunkId, String documentId, String clearance, String text) {
        static ContextChunk from(RetrievedChunk c) {
            return new ContextChunk(
                    String.valueOf(c.id()), String.valueOf(c.documentId()), c.clearance(), c.content());
        }
    }

    public static QueryResponse from(QaResult result, boolean includeContexts) {
        List<ContextChunk> contexts = includeContexts
                ? result.contexts().stream().map(ContextChunk::from).toList()
                : null;
        return new QueryResponse(result.answer(), result.citations(),
                RetrievalTrace.from(result.retrieval()), contexts, TokenUsage.from(result.usage()));
    }
}
