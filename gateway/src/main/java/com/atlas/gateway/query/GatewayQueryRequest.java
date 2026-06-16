package com.atlas.gateway.query;

/**
 * Client-facing {@code POST /v1/query} request (P3_SPEC §2.3). {@code topK} is optional (rag-engine
 * applies its configured default). {@code includeContexts} (default false) is forwarded to rag-engine —
 * the P2 eval-through-Gateway harness (task 10) sets it to retrieve the RBAC-filtered contexts RAGAS needs.
 */
public record GatewayQueryRequest(String query, Integer topK, Boolean includeContexts) {

    public boolean hasQuery() {
        return query != null && !query.isBlank();
    }
}
