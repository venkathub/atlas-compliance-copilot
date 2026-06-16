package com.atlas.gateway.query;

import com.atlas.gateway.auth.DownstreamClearanceSigner;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Thin client that proxies a query to {@code rag-engine}'s {@code POST /v1/query} (P3 task 3).
 *
 * <p>It attaches the Gateway-signed internal verified-clearance assertion (ADR-0034 / D-P3-5) in the
 * {@link DownstreamClearanceSigner#HEADER} header — this is how the trust boundary conveys a clearance
 * {@code rag-engine} can verify rather than trust. The response body is relayed verbatim as a
 * {@link JsonNode} (answer + citations + retrieval pass through losslessly); later tasks enrich this
 * envelope with routing/cache/redaction/cost (P3_SPEC §2.3).
 */
@Component
public class RagEngineClient {

    private final RestClient restClient;

    public RagEngineClient(RestClient ragEngineRestClient) {
        this.restClient = ragEngineRestClient;
    }

    /**
     * Forward {@code request} to rag-engine with the signed internal clearance assertion.
     *
     * @param internalAssertion serialized internal-hop JWT from {@link DownstreamClearanceSigner}
     * @param request           the client query to forward
     * @return rag-engine's JSON response body
     */
    public JsonNode query(String internalAssertion, GatewayQueryRequest request) {
        return restClient.post()
                .uri("/v1/query")
                .header(DownstreamClearanceSigner.HEADER, internalAssertion)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(JsonNode.class);
    }
}
