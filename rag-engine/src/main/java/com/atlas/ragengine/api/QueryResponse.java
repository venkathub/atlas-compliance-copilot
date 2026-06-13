package com.atlas.ragengine.api;

import com.atlas.ragengine.qa.Citation;
import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import java.util.List;

/** {@code POST /v1/query} response — the §2.4 contract: answer + citations + retrieval trace. */
public record QueryResponse(String answer, List<Citation> citations, RetrievalTrace retrieval) {

    /** The visible retrieval trace surfaced to the caller/UI. */
    public record RetrievalTrace(int denseHits, int sparseHits, int fused, int reranked,
            String clearanceApplied) {
        static RetrievalTrace from(RetrievalStats s) {
            return new RetrievalTrace(s.denseHits(), s.sparseHits(), s.fused(), s.reranked(),
                    s.clearanceApplied());
        }
    }

    public static QueryResponse from(QaResult result) {
        return new QueryResponse(result.answer(), result.citations(),
                RetrievalTrace.from(result.retrieval()));
    }
}
