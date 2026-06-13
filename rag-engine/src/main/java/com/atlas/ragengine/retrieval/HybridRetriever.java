package com.atlas.ragengine.retrieval;

import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalResult;
import com.atlas.ragengine.security.ClearanceLevel;

/**
 * Retrieval seam used by the QA layer. Implemented by {@link HybridDocumentRetriever}; lets
 * {@code QueryService} be unit-tested with a fake (no DB/model).
 */
public interface HybridRetriever {

    RetrievalResult retrieve(String query, ClearanceLevel caller, int topK);
}
