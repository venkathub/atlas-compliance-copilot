package com.atlas.ragengine.retrieval;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.security.ClearanceLevel;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * RBAC negative-access HARD GATE (D4, ADR-0012). For every golden case, runs the query at the
 * caller's clearance across <b>dense-only, sparse-only, and hybrid</b> paths and asserts that
 * <b>no returned chunk exceeds the caller's clearance</b> and <b>no forbidden document id appears</b>.
 *
 * <p>Any cross-clearance leak fails the build (P1_SPEC §4 — 0 leaks tolerated). The gate is
 * independent of embedding quality (it is enforced by the SQL predicate), so it holds under the
 * deterministic stub embedder used in CI.
 */
class RbacNegativeAccessIT {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final int DEEP_K = 50; // retrieve deeply to give any leak the chance to surface

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

    @TestFactory
    List<DynamicTest> negativeAccessGoldenCases() throws Exception {
        JsonNode root = JSON.readTree(new PathMatchingResourcePatternResolver()
                .getResource("classpath:fixtures/negative_access.json").getInputStream());

        List<DynamicTest> tests = new ArrayList<>();
        for (JsonNode c : root.get("cases")) {
            String caseId = c.get("id").asText();
            ClearanceLevel caller = ClearanceLevel.fromLabel(c.get("clearance").asText());
            String query = c.get("query").asText();
            Set<String> forbiddenClearances = strings(c.get("forbiddenClearances"));
            Set<String> forbiddenDocIds = strings(c.get("forbiddenDocIds"));

            tests.add(DynamicTest.dynamicTest(caseId + " :: dense", () ->
                    assertNoLeak(caseId, "dense", harness.dense.retrieve(query, caller, DEEP_K),
                            caller, forbiddenClearances, forbiddenDocIds)));
            tests.add(DynamicTest.dynamicTest(caseId + " :: sparse", () ->
                    assertNoLeak(caseId, "sparse", harness.sparse.retrieve(query, caller, DEEP_K),
                            caller, forbiddenClearances, forbiddenDocIds)));
            tests.add(DynamicTest.dynamicTest(caseId + " :: hybrid", () ->
                    assertNoLeak(caseId, "hybrid", harness.hybrid.retrieve(query, caller, DEEP_K).chunks(),
                            caller, forbiddenClearances, forbiddenDocIds)));
        }
        return tests;
    }

    private static void assertNoLeak(String caseId, String path, List<RetrievedChunk> chunks,
            ClearanceLevel caller, Set<String> forbiddenClearances, Set<String> forbiddenDocIds) {
        for (RetrievedChunk chunk : chunks) {
            // 1) no chunk above the caller's clearance (the core RBAC guarantee)
            assertThat(ClearanceLevel.fromLabel(chunk.clearance()).rank())
                    .as("%s/%s leaked chunk clearance '%s' (docId=%s) to caller '%s'",
                            caseId, path, chunk.clearance(), chunk.docId(), caller.label())
                    .isLessThanOrEqualTo(caller.rank());
            // 2) defense in depth: forbidden clearances / doc ids never appear
            assertThat(forbiddenClearances)
                    .as("%s/%s returned a forbidden clearance '%s'", caseId, path, chunk.clearance())
                    .doesNotContain(chunk.clearance());
            assertThat(forbiddenDocIds)
                    .as("%s/%s returned a forbidden docId '%s'", caseId, path, chunk.docId())
                    .doesNotContain(chunk.docId());
        }
    }

    private static Set<String> strings(JsonNode arr) {
        Set<String> out = new HashSet<>();
        if (arr != null) {
            arr.forEach(n -> out.add(n.asText()));
        }
        return out;
    }
}
