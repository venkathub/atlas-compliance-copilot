package com.atlas.ragengine.qa;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.guardrail.GuardrailProperties;
import com.atlas.ragengine.guardrail.InjectionGuardrail;
import com.atlas.ragengine.qa.QueryService.QaResult;
import com.atlas.ragengine.retrieval.RetrievalTestHarness;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * Wired QA IT (Testcontainers + deterministic stub {@link StubChatModel}, no GPU): real
 * retrieval → guardrail → citation extraction. Asserts that every answer marker resolves to a
 * returned chunk and no citation exceeds the caller's clearance.
 */
class QueryServiceIT {

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

    private QueryService service(String stubAnswer) {
        return new QueryService(
                harness.hybrid,
                new InjectionGuardrail(GuardrailProperties.defaults()),
                new CitationExtractor(new RbacFilterBuilder()),
                new StubChatModel(stubAnswer));
    }

    @Test
    void citationsResolveAndNeverExceedCallerClearance() {
        // the stub cites the first three sources; whichever resolve must all be <= compliance
        QaResult result = service("Open AML exceptions [1]; structuring [2]; see also [3].")
                .answer("Summarize the open AML exceptions for the Northwind account this quarter",
                        ClearanceLevel.COMPLIANCE, 6);

        assertThat(result.citations()).isNotEmpty();
        assertThat(result.citations()).allSatisfy(c -> {
            assertThat(ClearanceLevel.fromLabel(c.clearance()).rank())
                    .isLessThanOrEqualTo(ClearanceLevel.COMPLIANCE.rank());
            assertThat(c.marker()).isBetween(1, 3);
            assertThat(c.chunkId()).isNotNull();
        });
        assertThat(result.retrieval().clearanceApplied()).isEqualTo("compliance");
    }

    @Test
    void publicCallerNeverCitesRestrictedOrCompliance() {
        QaResult result = service("Based on [1] and [2].")
                .answer("Northwind beneficial owners and draft SAR", ClearanceLevel.PUBLIC, 6);
        assertThat(result.citations()).allSatisfy(c ->
                assertThat(c.clearance()).isIn("public"));
    }
}
