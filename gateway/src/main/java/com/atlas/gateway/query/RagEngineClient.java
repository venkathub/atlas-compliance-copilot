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
 * {@code rag-engine} can verify rather than trust — and the router-selected model tier (ADR-0035) in
 * the {@code X-Atlas-Model-Tier} header. The response body is relayed verbatim as a {@link JsonNode}.
 */
@Component
public class RagEngineClient {

    /** Header conveying the router-selected model tier to rag-engine (mirrors rag-engine's resolver). */
    public static final String MODEL_TIER_HEADER = "X-Atlas-Model-Tier";

    private final RestClient restClient;

    public RagEngineClient(RestClient ragEngineRestClient) {
        this.restClient = ragEngineRestClient;
    }

    /**
     * Forward {@code request} to rag-engine with the signed internal clearance assertion + model tier.
     *
     * @param internalAssertion serialized internal-hop JWT from {@link DownstreamClearanceSigner}
     * @param modelTier         the router-selected tier label (e.g. {@code tier1-small})
     * @param request           the client query to forward
     * @return rag-engine's JSON response body
     */
    public JsonNode query(String internalAssertion, String modelTier, GatewayQueryRequest request) {
        return restClient.post()
                .uri("/v1/query")
                .header(DownstreamClearanceSigner.HEADER, internalAssertion)
                .header(MODEL_TIER_HEADER, modelTier)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(JsonNode.class);
    }
}
