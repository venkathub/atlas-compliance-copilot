package com.atlas.gateway.query;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

/**
 * LIVE end-to-end test through the real stack: Gateway → a running {@code rag-engine} (real Ollama +
 * Postgres+pgvector). Mints a clearance token for Priya and asks the Northwind question through the
 * Gateway, asserting a grounded, cited answer comes back.
 *
 * <p>Gated behind the {@code live} tag/profile; never in CI. Bring up rag-engine (corpus ingested) +
 * the GPU first, then:
 * <pre>set -a &amp;&amp; . ./.env &amp;&amp; set +a &amp;&amp; mvn -P live -pl gateway verify</pre>
 * Point at a non-default rag-engine via {@code ATLAS_GATEWAY_RAG_ENGINE_URL}.
 */
@Tag("live")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class GatewayQueryLiveIT {

    private static final String NORTHWIND_QUESTION =
            "Summarize the open AML exceptions for the Northwind account this quarter.";

    @Autowired
    private TestRestTemplate rest;

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void citedAnswerThroughGatewayForCompliancePriya() throws Exception {
        String token = json.readTree(rest.postForEntity(
                "/v1/auth/token", "{\"user\":\"priya\"}", String.class).getBody()).get("token").asText();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);
        ResponseEntity<JsonNode> response = rest.exchange(
                "/v1/query", HttpMethod.POST,
                new HttpEntity<>("{\"query\":\"" + NORTHWIND_QUESTION + "\",\"topK\":6}", headers),
                JsonNode.class);

        assertThat(response.getStatusCode().is2xxSuccessful()).isTrue();
        JsonNode body = response.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("answer").asText()).isNotBlank();
        assertThat(body.get("retrieval").get("clearanceApplied").asText()).isEqualTo("compliance");
    }
}
