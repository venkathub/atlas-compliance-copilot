package com.atlas.ragengine.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.ingest.IngestionService.IngestionReport;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;

/**
 * LIVE end-to-end test against the real remote Ollama (chat + embeddings) and a running local
 * Postgres+pgvector. Drives the forcing story over HTTP: admin-ingest the corpus, then ask the
 * Northwind question as Priya (compliance) and as a public guest.
 *
 * <p>Gated behind the {@code live} tag/profile (needs a GPU + {@code make -C infra up}); never in CI:
 * <pre>set -a && . ./.env && set +a && mvn -P live -pl rag-engine verify</pre>
 */
@Tag("live")
@ActiveProfiles("local")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class QueryLiveIT {

    private static final String NORTHWIND_QUESTION =
            "Summarize the open AML exceptions for the Northwind account this quarter.";

    @Autowired
    TestRestTemplate rest;

    @Test
    void adminIngestThenCitedAnswerRespectsClearance() {
        // 1) admin (restricted) triggers a full rebuild
        ResponseEntity<IngestionReport> ingest = rest.exchange(
                "/v1/admin/ingest", HttpMethod.POST, new HttpEntity<>(headers("bsa-admin")),
                IngestionReport.class);
        assertThat(ingest.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(ingest.getBody()).isNotNull();
        assertThat(ingest.getBody().documents()).isEqualTo(24);

        // 2) a non-admin cannot ingest
        ResponseEntity<String> forbidden = rest.exchange(
                "/v1/admin/ingest", HttpMethod.POST, new HttpEntity<>(headers("priya")), String.class);
        assertThat(forbidden.getStatusCode().value()).isEqualTo(403);

        // 3) Priya (compliance) gets a grounded, cited answer; nothing above her clearance is cited
        ResponseEntity<QueryResponse> priya = rest.exchange(
                "/v1/query", HttpMethod.POST, query("priya", NORTHWIND_QUESTION), QueryResponse.class);
        assertThat(priya.getStatusCode().is2xxSuccessful()).isTrue();
        QueryResponse answer = priya.getBody();
        assertThat(answer).isNotNull();
        assertThat(answer.answer()).isNotBlank();
        assertThat(answer.retrieval().clearanceApplied()).isEqualTo("compliance");
        assertThat(answer.citations()).allSatisfy(c ->
                assertThat(c.clearance()).isIn("public", "analyst", "compliance"));

        // 4) a public guest asking the same question never sees compliance/restricted citations
        ResponseEntity<QueryResponse> guest = rest.exchange(
                "/v1/query", HttpMethod.POST, query("guest-public", NORTHWIND_QUESTION), QueryResponse.class);
        assertThat(guest.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(guest.getBody()).isNotNull();
        assertThat(guest.getBody().citations()).allSatisfy(c ->
                assertThat(c.clearance()).isEqualTo("public"));
    }

    private static HttpHeaders headers(String user) {
        HttpHeaders h = new HttpHeaders();
        h.add("X-Atlas-User", user);
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    private static HttpEntity<String> query(String user, String question) {
        return new HttpEntity<>("{\"query\":\"" + question + "\",\"topK\":6}", headers(user));
    }
}
