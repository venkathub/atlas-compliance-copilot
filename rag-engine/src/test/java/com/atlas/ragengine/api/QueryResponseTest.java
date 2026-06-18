package com.atlas.ragengine.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.qa.QueryService.QaResult.TokenUsage;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalStats;
import java.util.List;
import org.junit.jupiter.api.Test;

/** Mapping test: token usage (P3, ADR-0040) surfaces in the response only when present. */
class QueryResponseTest {

    private static final RetrievalStats STATS = new RetrievalStats(1, 0, 1, 1, "public");

    @Test
    void surfacesTokenUsageWhenPresent() {
        QaResult result = new QaResult("ans", List.of(), STATS, List.of(), new TokenUsage(812, 143));
        QueryResponse response = QueryResponse.from(result, false);

        assertThat(response.usage()).isNotNull();
        assertThat(response.usage().promptTokens()).isEqualTo(812);
        assertThat(response.usage().completionTokens()).isEqualTo(143);
    }

    @Test
    void omitsUsageWhenAbsent() {
        QaResult result = new QaResult("ans", List.of(), STATS);
        QueryResponse response = QueryResponse.from(result, false);
        assertThat(response.usage()).isNull();
    }
}
