package com.atlas.gateway.query;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.atlas.gateway.auth.SecurityKeys;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.SignedJWT;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.concurrent.TimeUnit;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * End-to-end query-path IT (P3 task 3): a real HTTP round-trip through the full gateway — JWT trust
 * boundary → query controller → {@link RagEngineClient} → a {@link MockWebServer} standing in for
 * rag-engine. Proves the authenticated pass-through and, crucially, that the Gateway puts a
 * <em>verifiable</em> internal clearance assertion (ADR-0034) on the wire. Model-free; no Docker/GPU.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class GatewayQueryIT {

    private static final String INTERNAL_SECRET = "it-internal-secret";
    private static final MockWebServer RAG_ENGINE = new MockWebServer();

    static {
        try {
            RAG_ENGINE.start();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("atlas.gateway.rag-engine-url", () -> RAG_ENGINE.url("/").toString());
        registry.add("atlas.gateway.internal-secret", () -> INTERNAL_SECRET);
        registry.add("atlas.idp.signing-key", () -> "it-signing-key");
        // This IT exercises auth + routing + passthrough + the circuit breaker; the Redis-backed semantic
        // cache, rate limiter, and budget are disabled here (covered by their own Testcontainer ITs).
        registry.add("atlas.cache.enabled", () -> "false");
        registry.add("atlas.resilience.rate-limit-enabled", () -> "false");
        registry.add("atlas.resilience.budget-enabled", () -> "false");
    }

    @AfterAll
    static void tearDown() throws IOException {
        RAG_ENGINE.shutdown();
    }

    @Autowired
    private TestRestTemplate rest;

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void authenticatedQueryProxiesWithVerifiableInternalAssertion() throws Exception {
        // rag-engine stub answer
        RAG_ENGINE.enqueue(new MockResponse()
                .setHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .setBody("{\"answer\":\"Open exceptions [1].\",\"citations\":[],"
                        + "\"retrieval\":{\"clearanceApplied\":\"compliance\"}}"));

        String token = mintToken("priya");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);
        ResponseEntity<JsonNode> response = rest.exchange(
                "/v1/query", org.springframework.http.HttpMethod.POST,
                new HttpEntity<>("{\"query\":\"aml exceptions?\",\"topK\":6}", headers), JsonNode.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().get("answer").asText()).isEqualTo("Open exceptions [1].");
        // Router merged a §2.3 routing section; a short query stays on the default tier.
        assertThat(response.getBody().get("routing").get("modelTier").asText()).isEqualTo("tier1-small");
        assertThat(response.getBody().get("routing").get("escalated").asBoolean()).isFalse();

        // The Gateway must have forwarded a VERIFIABLE internal clearance assertion for the caller.
        RecordedRequest forwarded = RAG_ENGINE.takeRequest(2, TimeUnit.SECONDS);
        assertThat(forwarded).isNotNull();
        assertThat(forwarded.getPath()).isEqualTo("/v1/query");
        String assertion = forwarded.getHeader(DownstreamClearanceSigner.HEADER);
        assertThat(assertion).isNotBlank();

        SignedJWT jwt = SignedJWT.parse(assertion);
        assertThat(jwt.verify(new MACVerifier(SecurityKeys.deriveHs256(INTERNAL_SECRET)))).isTrue();
        assertThat(jwt.getJWTClaimsSet().getStringClaim("clearance")).isEqualTo("compliance");
        assertThat(jwt.getJWTClaimsSet().getIssuer()).isEqualTo(DownstreamClearanceSigner.ISSUER);
    }

    @Test
    void unauthenticatedQueryIsRejectedBeforeReachingRagEngine() {
        ResponseEntity<String> response = rest.postForEntity("/v1/query",
                "{\"query\":\"aml?\"}", String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void downstreamErrorTripsTheBreakerFallbackTo503() throws Exception {
        RAG_ENGINE.enqueue(new MockResponse().setResponseCode(500)); // rag-engine failure
        String token = mintToken("priya");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);
        ResponseEntity<String> response = rest.exchange(
                "/v1/query", org.springframework.http.HttpMethod.POST,
                new HttpEntity<>("{\"query\":\"aml?\",\"topK\":6}", headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(response.getHeaders().getFirst(HttpHeaders.RETRY_AFTER)).isNotBlank();
    }

    private String mintToken(String user) throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<String> tokenResponse = rest.exchange(
                "/v1/auth/token", org.springframework.http.HttpMethod.POST,
                new HttpEntity<>("{\"user\":\"" + user + "\"}", headers), String.class);
        assertThat(tokenResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        return json.readTree(tokenResponse.getBody()).get("token").asText();
    }
}
