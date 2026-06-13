package com.atlas.ragengine.retrieval;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.retrieval.HybridDocumentRetriever.RetrievalResult;
import com.atlas.ragengine.security.ClearanceLevel;
import java.util.List;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * Demonstrates hybrid retrieval value (the sparse path surfaces rare keywords) and that the RBAC
 * predicate applies on the sparse path too. Embedding-quality-independent assertions only (the dense
 * path uses the deterministic stub embedder); real dense relevance is exercised by the live test.
 */
class HybridRetrievalIT {

    // a rare token that appears in exactly one (analyst-clearance) chunk: 3M_2022_10K MD&A
    private static final String RARE_KEYWORD = "Zwijndrecht";

    private static RetrievalTestHarness harness;

    @BeforeAll
    static void setUp() {
        harness = RetrievalTestHarness.start();
    }

    @AfterAll
    static void tearDown() {
        if (harness != null) {
            harness.close();
        }
    }

    @Test
    void sparsePathSurfacesRareKeyword() {
        List<RetrievedChunk> hits = harness.sparse.retrieve(RARE_KEYWORD, ClearanceLevel.ANALYST, 10);
        assertThat(hits).isNotEmpty();
        assertThat(hits.get(0).content()).contains(RARE_KEYWORD);
        // and it flows through fusion into the hybrid result
        RetrievalResult hybrid = harness.hybrid.retrieve(RARE_KEYWORD, ClearanceLevel.ANALYST, 10);
        assertThat(hybrid.chunks()).anyMatch(c -> c.content().contains(RARE_KEYWORD));
    }

    @Test
    void rbacAppliesOnSparsePath() {
        // the rare keyword lives in an analyst-clearance chunk; a public caller must get nothing
        List<RetrievedChunk> publicHits = harness.sparse.retrieve(RARE_KEYWORD, ClearanceLevel.PUBLIC, 10);
        assertThat(publicHits).isEmpty();
    }

    @Test
    void hybridOrderingIsDeterministic() {
        String query = "Summarize the open AML exceptions for the Northwind account this quarter";
        List<RetrievedChunk> first =
                harness.hybrid.retrieve(query, ClearanceLevel.COMPLIANCE, 6).chunks();
        List<RetrievedChunk> second =
                harness.hybrid.retrieve(query, ClearanceLevel.COMPLIANCE, 6).chunks();
        assertThat(second).extracting(RetrievedChunk::id)
                .isEqualTo(first.stream().map(RetrievedChunk::id).toList());
    }

    @Test
    void retrievalStatsArePopulated() {
        RetrievalResult result = harness.hybrid.retrieve(
                "structuring cash deposits", ClearanceLevel.COMPLIANCE, 6);
        assertThat(result.stats().clearanceApplied()).isEqualTo("compliance");
        assertThat(result.stats().reranked()).isEqualTo(result.chunks().size());
        assertThat(result.stats().fused()).isGreaterThanOrEqualTo(result.stats().reranked());
    }
}
